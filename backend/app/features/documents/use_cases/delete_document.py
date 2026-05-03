from __future__ import annotations

from typing import Protocol

from app.core.domain.ids import DocumentId
from app.features.ingest.entities.document import Document


class _DocumentRepository(Protocol):
    async def get(self, document_id: DocumentId) -> Document: ...

    async def delete(self, document_id: DocumentId) -> None: ...


class _VectorIndex(Protocol):
    async def delete_document(self, document_id: DocumentId) -> None: ...


class _UoW(Protocol):
    async def commit(self) -> None: ...


class DeleteDocumentUseCase:
    def __init__(
        self,
        *,
        documents: _DocumentRepository,
        vectors: _VectorIndex,
        uow: _UoW,
    ) -> None:
        self._documents = documents
        self._vectors = vectors
        self._uow = uow

    async def execute(self, document_id: DocumentId) -> None:
        await self._documents.get(document_id)
        await self._vectors.delete_document(document_id)
        await self._documents.delete(document_id)
        await self._uow.commit()


__all__ = ["DeleteDocumentUseCase"]
