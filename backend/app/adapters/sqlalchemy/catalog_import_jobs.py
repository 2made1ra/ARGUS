from __future__ import annotations

from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sqlalchemy.models import CatalogImportJob as CatalogImportJobModel
from app.features.catalog.entities.import_job import CatalogImportJob
from app.features.catalog.ports import CatalogImportJobNotFound


class SqlAlchemyCatalogImportJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: CatalogImportJob) -> None:
        await self._session.execute(
            insert(CatalogImportJobModel).values(**_job_values(job)),
        )

    async def get(self, job_id: UUID) -> CatalogImportJob:
        row = await self._session.scalar(
            select(CatalogImportJobModel).where(CatalogImportJobModel.id == job_id),
        )
        if row is None:
            raise CatalogImportJobNotFound(job_id)
        return _job_to_entity(row)

    async def update(self, job: CatalogImportJob) -> None:
        await self._session.execute(
            update(CatalogImportJobModel)
            .where(CatalogImportJobModel.id == job.id)
            .values(**_job_values(job)),
        )


def _job_values(job: CatalogImportJob) -> dict[str, object]:
    return {
        "id": job.id,
        "filename": job.filename,
        "source_path": job.source_path,
        "file_size_bytes": job.file_size_bytes,
        "status": job.status,
        "stage": job.stage,
        "progress_percent": job.progress_percent,
        "stage_progress_percent": job.stage_progress_percent,
        "row_count": job.row_count,
        "valid_row_count": job.valid_row_count,
        "invalid_row_count": job.invalid_row_count,
        "index_total": job.index_total,
        "indexed": job.indexed,
        "embedding_failed": job.embedding_failed,
        "indexing_failed": job.indexing_failed,
        "skipped": job.skipped,
        "import_batch_id": job.import_batch_id,
        "source_file_id": job.source_file_id,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "completed_at": job.completed_at,
    }


def _job_to_entity(row: CatalogImportJobModel) -> CatalogImportJob:
    return CatalogImportJob(
        id=row.id,
        filename=row.filename,
        source_path=row.source_path,
        file_size_bytes=row.file_size_bytes,
        status=row.status,  # type: ignore[arg-type]
        stage=row.stage,  # type: ignore[arg-type]
        progress_percent=row.progress_percent,
        stage_progress_percent=row.stage_progress_percent,
        row_count=row.row_count,
        valid_row_count=row.valid_row_count,
        invalid_row_count=row.invalid_row_count,
        index_total=row.index_total,
        indexed=row.indexed,
        embedding_failed=row.embedding_failed,
        indexing_failed=row.indexing_failed,
        skipped=row.skipped,
        import_batch_id=row.import_batch_id,
        source_file_id=row.source_file_id,
        error_message=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


__all__ = ["SqlAlchemyCatalogImportJobRepository"]
