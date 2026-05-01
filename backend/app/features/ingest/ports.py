from typing import Protocol, runtime_checkable

from app.core.domain.ids import DocumentId
from app.features.ingest.entities.document import Document


class DocumentNotFound(Exception):
    def __init__(self, document_id: DocumentId) -> None:
        super().__init__(f"Document not found: {document_id}")
        self.document_id = document_id


@runtime_checkable
class DocumentRepository(Protocol):
    async def add(self, document: Document) -> None: ...

    async def get(self, document_id: DocumentId) -> Document: ...

    async def list(self, *, limit: int, offset: int) -> list[Document]: ...

    async def update_status(self, document_id: DocumentId, status: str) -> None: ...

    async def set_error(self, document_id: DocumentId, message: str) -> None: ...


__all__ = ["DocumentNotFound", "DocumentRepository"]
