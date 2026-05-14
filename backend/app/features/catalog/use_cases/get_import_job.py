from __future__ import annotations

from uuid import UUID

from app.features.catalog.entities.import_job import CatalogImportJob
from app.features.catalog.ports import CatalogImportJobRepository


class GetCatalogImportJobUseCase:
    def __init__(self, *, jobs: CatalogImportJobRepository) -> None:
        self._jobs = jobs

    async def execute(self, job_id: UUID) -> CatalogImportJob:
        return await self._jobs.get(job_id)


__all__ = ["GetCatalogImportJobUseCase"]
