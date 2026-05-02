from __future__ import annotations

from app.core.domain.ids import DocumentId
from app.features.documents.dto import DocumentDTO, document_to_dto
from app.features.documents.ports import DocumentReader


class GetDocumentUseCase:
    def __init__(self, *, documents: DocumentReader) -> None:
        self._documents = documents

    async def execute(self, document_id: DocumentId) -> DocumentDTO:
        document = await self._documents.get(document_id)
        return document_to_dto(document)


__all__ = ["GetDocumentUseCase"]
