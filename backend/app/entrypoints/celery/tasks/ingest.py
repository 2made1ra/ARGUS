import asyncio
from collections.abc import Coroutine
from typing import Any
from uuid import UUID

from app.celery_app import celery_app
from app.core.domain.ids import DocumentId
from app.entrypoints.celery.composition import (
    build_document_repository,
    build_index_uc,
    build_process_uc,
    build_resolve_uc,
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


__all__ = [
    "index_document",
    "process_document",
    "resolve_contractor",
    "run_async",
]
