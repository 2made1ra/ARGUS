from __future__ import annotations

from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from app.entrypoints.celery.tasks import ingest
from app.features.catalog.entities.import_job import CatalogImportJob
from app.features.catalog.use_cases.import_prices_csv import (
    ImportPricesCsvProgress,
    PriceImportSummary,
)
from app.features.catalog.use_cases.index_price_items import (
    IndexPriceItemsProgress,
    IndexPriceItemsResult,
)


def _job(source_path: Path) -> CatalogImportJob:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return CatalogImportJob(
        id=uuid4(),
        filename="prices.csv",
        source_path=str(source_path),
        file_size_bytes=3,
        status="QUEUED",
        stage="upload",
        progress_percent=10,
        stage_progress_percent=100,
        row_count=0,
        valid_row_count=0,
        invalid_row_count=0,
        index_total=0,
        indexed=0,
        embedding_failed=0,
        indexing_failed=0,
        skipped=0,
        import_batch_id=None,
        source_file_id=None,
        error_message=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )


class FakeCatalogImportJobRepository:
    def __init__(self, job: CatalogImportJob) -> None:
        self.job = job
        self.history: list[CatalogImportJob] = []

    async def get(self, job_id: UUID) -> CatalogImportJob:
        assert job_id == self.job.id
        return self.job

    async def update(self, job: CatalogImportJob) -> None:
        self.job = job
        self.history.append(deepcopy(job))


class FakeUnitOfWork:
    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeImportPricesCsvUseCase:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, object]] = []
        self.import_batch_id = uuid4()
        self.source_file_id = uuid4()

    async def execute(
        self,
        *,
        filename: str,
        content: bytes,
        source_path: str | None,
        progress_callback,
    ) -> PriceImportSummary:
        self.calls.append(
            {
                "filename": filename,
                "content": content,
                "source_path": source_path,
            },
        )
        if self.error is not None:
            raise self.error
        await progress_callback(
            ImportPricesCsvProgress(
                total_rows=2,
                processed_rows=2,
                valid_row_count=2,
                invalid_row_count=0,
                import_batch_id=self.import_batch_id,
                source_file_id=self.source_file_id,
                done=True,
            ),
        )
        return PriceImportSummary(
            id=self.import_batch_id,
            source_file_id=self.source_file_id,
            filename=filename,
            status="IMPORTED",
            row_count=2,
            valid_row_count=2,
            invalid_row_count=0,
            embedding_template_version="prices_v1",
            embedding_model="nomic-embed-text-v1.5",
        )


class FakeIndexPriceItemsUseCase:
    def __init__(
        self,
        *,
        embedding_failed: int = 0,
        indexing_failed: int = 0,
    ) -> None:
        self.embedding_failed = embedding_failed
        self.indexing_failed = indexing_failed
        self.calls: list[dict[str, object]] = []

    async def execute(
        self,
        *,
        limit: int | None,
        import_batch_id: UUID | None,
        progress_callback,
    ) -> IndexPriceItemsResult:
        self.calls.append({"limit": limit, "import_batch_id": import_batch_id})
        await progress_callback(
            IndexPriceItemsProgress(
                total=2,
                processed=2,
                indexed=2 - self.embedding_failed - self.indexing_failed,
                embedding_failed=self.embedding_failed,
                indexing_failed=self.indexing_failed,
                skipped=0,
                done=True,
            ),
        )
        return IndexPriceItemsResult(
            total=2,
            indexed=2 - self.embedding_failed - self.indexing_failed,
            embedding_failed=self.embedding_failed,
            indexing_failed=self.indexing_failed,
        )


@pytest.mark.asyncio
async def test_import_and_index_catalog_job_marks_completed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "prices.csv"
    source.write_bytes(b"csv")
    job = _job(source)
    repository = FakeCatalogImportJobRepository(job)
    import_uc = FakeImportPricesCsvUseCase()
    index_uc = FakeIndexPriceItemsUseCase()

    monkeypatch.setattr(
        ingest,
        "build_catalog_import_job_repository",
        lambda: (repository, FakeUnitOfWork()),
    )
    monkeypatch.setattr(ingest, "build_import_prices_csv_uc", lambda: import_uc)

    @asynccontextmanager
    async def fake_index_builder():
        yield index_uc

    monkeypatch.setattr(ingest, "build_catalog_index_uc", fake_index_builder)

    await ingest._import_and_index_catalog_job(str(job.id))

    assert repository.job.status == "COMPLETED"
    assert repository.job.stage == "completed"
    assert repository.job.progress_percent == 100
    assert repository.job.row_count == 2
    assert repository.job.index_total == 2
    assert repository.job.indexed == 2
    assert import_uc.calls == [
        {
            "filename": "prices.csv",
            "content": b"csv",
            "source_path": str(source),
        },
    ]
    assert index_uc.calls == [
        {"limit": None, "import_batch_id": import_uc.import_batch_id},
    ]
    assert [snapshot.status for snapshot in repository.history] == [
        "IMPORTING",
        "IMPORTING",
        "IMPORTING",
        "INDEXING",
        "INDEXING",
        "INDEXING",
        "COMPLETED",
    ]


@pytest.mark.asyncio
async def test_import_and_index_catalog_job_marks_failed_on_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "prices.csv"
    source.write_bytes(b"csv")
    job = _job(source)
    repository = FakeCatalogImportJobRepository(job)
    import_uc = FakeImportPricesCsvUseCase(error=RuntimeError("csv exploded"))

    monkeypatch.setattr(
        ingest,
        "build_catalog_import_job_repository",
        lambda: (repository, FakeUnitOfWork()),
    )
    monkeypatch.setattr(ingest, "build_import_prices_csv_uc", lambda: import_uc)

    await ingest._import_and_index_catalog_job(str(job.id))

    assert repository.job.status == "FAILED"
    assert repository.job.stage == "failed"
    assert repository.job.error_message == "csv exploded"
    assert repository.job.completed_at is not None
    assert [snapshot.status for snapshot in repository.history] == [
        "IMPORTING",
        "FAILED",
    ]


@pytest.mark.asyncio
async def test_import_and_index_catalog_job_marks_failed_on_index_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "prices.csv"
    source.write_bytes(b"csv")
    job = _job(source)
    repository = FakeCatalogImportJobRepository(job)
    import_uc = FakeImportPricesCsvUseCase()
    index_uc = FakeIndexPriceItemsUseCase(embedding_failed=1, indexing_failed=1)

    monkeypatch.setattr(
        ingest,
        "build_catalog_import_job_repository",
        lambda: (repository, FakeUnitOfWork()),
    )
    monkeypatch.setattr(ingest, "build_import_prices_csv_uc", lambda: import_uc)

    @asynccontextmanager
    async def fake_index_builder():
        yield index_uc

    monkeypatch.setattr(ingest, "build_catalog_index_uc", fake_index_builder)

    await ingest._import_and_index_catalog_job(str(job.id))

    assert repository.job.status == "FAILED"
    assert repository.job.stage == "failed"
    assert repository.job.error_message == (
        "Catalog indexing failed: embedding_failed=1, indexing_failed=1"
    )
    assert repository.job.index_total == 2
    assert repository.job.embedding_failed == 1
    assert repository.job.indexing_failed == 1
    assert repository.job.completed_at is not None
