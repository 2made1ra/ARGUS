from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import UUID

from app.features.catalog.entities.import_job import CatalogImportJob
from app.features.catalog.use_cases.start_import_job import StartCatalogImportJobUseCase


class FakeCatalogImportStorage:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.saved_job_id: UUID | None = None

    async def save(
        self,
        job_id: UUID,
        stream: BytesIO,
        filename: str,
    ) -> tuple[Path, int]:
        self.calls.append("save")
        self.saved_job_id = job_id
        return Path(f"/tmp/{job_id}-{filename}"), len(stream.read())


class FakeCatalogImportJobRepository:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.jobs: list[CatalogImportJob] = []

    async def add(self, job: CatalogImportJob) -> None:
        self.calls.append("add")
        self.jobs.append(job)

    async def update(self, job: CatalogImportJob) -> None:
        self.calls.append("update")
        self.jobs = [job if item.id == job.id else item for item in self.jobs]


class FakeCatalogImportTaskQueue:
    def __init__(self, calls: list[str], error: Exception | None = None) -> None:
        self.calls = calls
        self.error = error
        self.enqueued: list[UUID] = []

    async def enqueue_import_and_index(self, job_id: UUID) -> None:
        self.calls.append("enqueue")
        if self.error is not None:
            raise self.error
        self.enqueued.append(job_id)


class FakeUnitOfWork:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.calls.append("commit")

    async def rollback(self) -> None:
        self.calls.append("rollback")


async def test_start_import_job_saves_adds_commits_then_enqueues() -> None:
    calls: list[str] = []
    storage = FakeCatalogImportStorage(calls)
    jobs = FakeCatalogImportJobRepository(calls)
    tasks = FakeCatalogImportTaskQueue(calls)

    use_case = StartCatalogImportJobUseCase(
        storage=storage,
        jobs=jobs,
        tasks=tasks,
        uow=FakeUnitOfWork(calls),
    )

    job = await use_case.execute(file=BytesIO(b"csv"), filename="prices.csv")

    assert calls == ["save", "add", "commit", "enqueue"]
    assert storage.saved_job_id == job.id
    assert jobs.jobs == [job]
    assert tasks.enqueued == [job.id]
    assert job.status == "QUEUED"
    assert job.stage == "upload"
    assert job.progress_percent == 10
    assert job.stage_progress_percent == 100
    assert job.source_path == f"/tmp/{job.id}-prices.csv"
    assert job.file_size_bytes == 3


async def test_start_import_job_marks_failed_when_enqueue_fails() -> None:
    calls: list[str] = []
    jobs = FakeCatalogImportJobRepository(calls)
    use_case = StartCatalogImportJobUseCase(
        storage=FakeCatalogImportStorage(calls),
        jobs=jobs,
        tasks=FakeCatalogImportTaskQueue(calls, error=RuntimeError("redis down")),
        uow=FakeUnitOfWork(calls),
    )

    try:
        await use_case.execute(file=BytesIO(b"csv"), filename="prices.csv")
    except RuntimeError as exc:
        assert str(exc) == "redis down"
    else:
        raise AssertionError("Expected enqueue failure")

    assert calls == ["save", "add", "commit", "enqueue", "update", "commit"]
    assert len(jobs.jobs) == 1
    assert jobs.jobs[0].status == "FAILED"
    assert jobs.jobs[0].stage == "failed"
    assert jobs.jobs[0].error_message == "redis down"
    assert jobs.jobs[0].completed_at is not None
