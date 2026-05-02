from app.celery_app import celery_app
from app.core.domain.ids import DocumentId
from app.features.ingest.ports import IngestionTaskQueue


class CeleryIngestionTaskQueue(IngestionTaskQueue):
    async def enqueue_process(self, document_id: DocumentId) -> None:
        celery_app.send_task("ingest.process_document", args=[str(document_id)])

    async def enqueue_resolve(self, document_id: DocumentId) -> None:
        celery_app.send_task("ingest.resolve_contractor", args=[str(document_id)])

    async def enqueue_index(self, document_id: DocumentId) -> None:
        celery_app.send_task("ingest.index_document", args=[str(document_id)])


__all__ = ["CeleryIngestionTaskQueue"]
