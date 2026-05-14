from __future__ import annotations

from datetime import UTC, datetime
from typing import BinaryIO
from uuid import uuid4

from app.features.catalog.entities.import_job import CatalogImportJob
from app.features.catalog.ports import (
    CatalogImportFileStorage,
    CatalogImportJobRepository,
    CatalogImportTaskQueue,
    UnitOfWork,
)


class StartCatalogImportJobUseCase:
    def __init__(
        self,
        *,
        storage: CatalogImportFileStorage,
        jobs: CatalogImportJobRepository,
        tasks: CatalogImportTaskQueue,
        uow: UnitOfWork,
    ) -> None:
        self._storage = storage
        self._jobs = jobs
        self._tasks = tasks
        self._uow = uow

    async def execute(self, *, file: BinaryIO, filename: str) -> CatalogImportJob:
        job_id = uuid4()
        path, size = await self._storage.save(job_id, file, filename)
        now = datetime.now(UTC)
        job = CatalogImportJob(
            id=job_id,
            filename=filename,
            source_path=str(path),
            file_size_bytes=size,
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

        async with self._uow:
            await self._jobs.add(job)
            await self._uow.commit()

        try:
            await self._tasks.enqueue_import_and_index(job.id)
        except Exception as exc:
            job.status = "FAILED"
            job.stage = "failed"
            job.error_message = str(exc)
            now = datetime.now(UTC)
            job.updated_at = now
            job.completed_at = now
            async with self._uow:
                await self._jobs.update(job)
                await self._uow.commit()
            raise
        return job


__all__ = ["StartCatalogImportJobUseCase"]
