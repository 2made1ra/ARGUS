import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.celery_app import celery_app
from app.core.domain.ids import DocumentId
from app.entrypoints.celery.composition import (
    build_catalog_import_job_repository,
    build_catalog_index_uc,
    build_document_repository,
    build_import_prices_csv_uc,
    build_index_uc,
    build_process_uc,
    build_resolve_uc,
)
from app.features.catalog.entities.import_job import CatalogImportJob
from app.features.catalog.use_cases.import_prices_csv import (
    ImportPricesCsvProgress,
)
from app.features.catalog.use_cases.index_price_items import (
    IndexPriceItemsProgress,
)
from app.features.ingest.entities.document import DocumentStatus


def _worker_loop() -> asyncio.AbstractEventLoop:
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            return loop
    except RuntimeError:
        pass
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    return _worker_loop().run_until_complete(coro)


async def _mark_status(document_id: str, status: str) -> None:
    documents, uow = build_document_repository()
    async with uow:
        await documents.update_status(
            DocumentId(UUID(document_id)),
            DocumentStatus(status),
        )
        await uow.commit()


async def _index_document(document_id: str) -> None:
    async with build_index_uc() as use_case:
        await use_case.execute(DocumentId(UUID(document_id)))


async def _get_catalog_job(job_id: UUID) -> CatalogImportJob:
    jobs, uow = build_catalog_import_job_repository()
    async with uow:
        return await jobs.get(job_id)


async def _update_catalog_job(job: CatalogImportJob) -> None:
    job.updated_at = datetime.now(UTC)
    jobs, uow = build_catalog_import_job_repository()
    async with uow:
        await jobs.update(job)
        await uow.commit()


async def _mark_catalog_job_importing(job_id: UUID) -> CatalogImportJob:
    job = await _get_catalog_job(job_id)
    job.status = "IMPORTING"
    job.stage = "import"
    job.progress_percent = 10
    job.stage_progress_percent = 0
    job.error_message = None
    await _update_catalog_job(job)
    return job


async def _mark_catalog_job_indexing(job_id: UUID) -> CatalogImportJob:
    job = await _get_catalog_job(job_id)
    job.status = "INDEXING"
    job.stage = "indexing"
    job.progress_percent = 35
    job.stage_progress_percent = 0
    await _update_catalog_job(job)
    return job


async def _mark_catalog_job_completed(job_id: UUID) -> None:
    job = await _get_catalog_job(job_id)
    job.status = "COMPLETED"
    job.stage = "completed"
    job.progress_percent = 100
    job.stage_progress_percent = 100
    job.error_message = None
    job.completed_at = datetime.now(UTC)
    await _update_catalog_job(job)


async def _mark_catalog_job_failed(job_id: UUID, error_message: str) -> None:
    job = await _get_catalog_job(job_id)
    job.status = "FAILED"
    job.stage = "failed"
    job.error_message = error_message
    job.completed_at = datetime.now(UTC)
    await _update_catalog_job(job)


async def _fail_catalog_job_after_indexing(
    job_id: UUID,
    *,
    embedding_failed: int,
    indexing_failed: int,
) -> None:
    await _mark_catalog_job_failed(
        job_id,
        (
            "Catalog indexing failed: "
            f"embedding_failed={embedding_failed}, "
            f"indexing_failed={indexing_failed}"
        ),
    )


async def _update_catalog_import_progress(
    job_id: UUID,
    event: ImportPricesCsvProgress,
) -> None:
    stage_progress = _percent(event.processed_rows, event.total_rows)
    if event.done:
        stage_progress = 100
    job = await _get_catalog_job(job_id)
    job.status = "IMPORTING"
    job.stage = "import"
    job.stage_progress_percent = stage_progress
    job.progress_percent = 10 + ((stage_progress * 25) // 100)
    job.row_count = event.total_rows
    job.valid_row_count = event.valid_row_count
    job.invalid_row_count = event.invalid_row_count
    job.import_batch_id = event.import_batch_id
    job.source_file_id = event.source_file_id
    await _update_catalog_job(job)


async def _update_catalog_index_progress(
    job_id: UUID,
    event: IndexPriceItemsProgress,
) -> None:
    stage_progress = _percent(event.processed, event.total)
    if event.done:
        stage_progress = 100
    job = await _get_catalog_job(job_id)
    job.status = "INDEXING"
    job.stage = "indexing"
    job.stage_progress_percent = stage_progress
    job.progress_percent = 35 + ((stage_progress * 65) // 100)
    job.index_total = event.total
    job.indexed = event.indexed
    job.embedding_failed = event.embedding_failed
    job.indexing_failed = event.indexing_failed
    job.skipped = event.skipped
    await _update_catalog_job(job)


def _percent(done: int, total: int) -> int:
    if total <= 0:
        return 100
    return max(0, min(100, int((done / total) * 100)))


async def _import_and_index_catalog_job(job_id: str) -> None:
    parsed_job_id = UUID(job_id)
    try:
        job = await _mark_catalog_job_importing(parsed_job_id)

        async def import_progress(event: ImportPricesCsvProgress) -> None:
            await _update_catalog_import_progress(parsed_job_id, event)

        import_summary = await build_import_prices_csv_uc().execute(
            filename=job.filename,
            content=await asyncio.to_thread(Path(job.source_path).read_bytes),
            source_path=job.source_path,
            progress_callback=import_progress,
        )
        job = await _get_catalog_job(parsed_job_id)
        job.row_count = import_summary.row_count
        job.valid_row_count = import_summary.valid_row_count
        job.invalid_row_count = import_summary.invalid_row_count
        job.import_batch_id = import_summary.id
        job.source_file_id = import_summary.source_file_id
        job.progress_percent = 35
        job.stage_progress_percent = 100
        await _update_catalog_job(job)

        await _mark_catalog_job_indexing(parsed_job_id)

        async def index_progress(event: IndexPriceItemsProgress) -> None:
            await _update_catalog_index_progress(parsed_job_id, event)

        async with build_catalog_index_uc() as use_case:
            index_result = await use_case.execute(
                limit=None,
                import_batch_id=import_summary.id,
                progress_callback=index_progress,
            )
        job = await _get_catalog_job(parsed_job_id)
        job.index_total = index_result.total
        job.indexed = index_result.indexed
        job.embedding_failed = index_result.embedding_failed
        job.indexing_failed = index_result.indexing_failed
        job.skipped = index_result.skipped
        await _update_catalog_job(job)

        if index_result.embedding_failed > 0 or index_result.indexing_failed > 0:
            await _fail_catalog_job_after_indexing(
                parsed_job_id,
                embedding_failed=index_result.embedding_failed,
                indexing_failed=index_result.indexing_failed,
            )
            return

        await _mark_catalog_job_completed(parsed_job_id)
    except Exception as exc:
        await _mark_catalog_job_failed(parsed_job_id, str(exc))


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="ingest.process_document",
    max_retries=3,
    default_retry_delay=30,
)
def process_document(self: Any, document_id: str) -> None:
    run_async(build_process_uc().execute(DocumentId(UUID(document_id))))
    celery_app.send_task("ingest.resolve_contractor", args=[document_id])


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="ingest.resolve_contractor",
    max_retries=3,
    default_retry_delay=30,
)
def resolve_contractor(self: Any, document_id: str) -> None:
    run_async(_mark_status(document_id, "RESOLVING"))
    run_async(build_resolve_uc().execute(DocumentId(UUID(document_id))))
    celery_app.send_task("ingest.index_document", args=[document_id])


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="ingest.index_document",
    max_retries=3,
    default_retry_delay=30,
)
def index_document(self: Any, document_id: str) -> None:
    run_async(_index_document(document_id))


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="catalog.import_and_index_job",
)
def import_and_index_catalog_job(self: Any, job_id: str) -> None:
    run_async(_import_and_index_catalog_job(job_id))


__all__ = [
    "import_and_index_catalog_job",
    "index_document",
    "process_document",
    "resolve_contractor",
    "run_async",
]
