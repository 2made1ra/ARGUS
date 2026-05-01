from datetime import UTC, datetime
from typing import BinaryIO

from app.core.domain.ids import DocumentId, new_document_id
from app.core.ports.unit_of_work import UnitOfWork
from app.features.ingest.entities.document import Document, DocumentStatus
from app.features.ingest.ports import (
    DocumentFileStorage,
    DocumentRepository,
    IngestionTaskQueue,
)


class UploadDocumentUseCase:
    def __init__(
        self,
        *,
        storage: DocumentFileStorage,
        documents: DocumentRepository,
        tasks: IngestionTaskQueue,
        uow: UnitOfWork,
    ) -> None:
        self._storage = storage
        self._documents = documents
        self._tasks = tasks
        self._uow = uow

    async def execute(
        self,
        *,
        file: BinaryIO,
        filename: str,
        content_type: str,
    ) -> DocumentId:
        path = await self._storage.save(file, filename)
        document = Document(
            id=new_document_id(),
            contractor_entity_id=None,
            title=filename,
            file_path=str(path),
            content_type=content_type,
            document_kind=None,
            doc_type=None,
            status=DocumentStatus.QUEUED,
            error_message=None,
            partial_extraction=False,
            created_at=datetime.now(UTC),
        )

        async with self._uow:
            await self._documents.add(document)
            await self._uow.commit()

        await self._tasks.enqueue_process(document.id)
        return document.id


__all__ = ["UploadDocumentUseCase"]
