from __future__ import annotations

from uuid import UUID

from app.celery_app import celery_app
from app.features.catalog.ports import CatalogImportTaskQueue


class CeleryCatalogImportTaskQueue(CatalogImportTaskQueue):
    async def enqueue_import_and_index(self, job_id: UUID) -> None:
        celery_app.send_task("catalog.import_and_index_job", args=[str(job_id)])


__all__ = ["CeleryCatalogImportTaskQueue"]
