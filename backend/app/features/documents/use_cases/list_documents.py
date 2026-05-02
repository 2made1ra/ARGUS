from __future__ import annotations

from app.core.domain.ids import ContractorEntityId
from app.features.documents.dto import DocumentDTO, document_to_dto
from app.features.documents.ports import DocumentListReader
from app.features.ingest.entities.document import DocumentStatus


class ListDocumentsUseCase:
    def __init__(self, *, documents: DocumentListReader) -> None:
        self._documents = documents

    async def execute(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: DocumentStatus | None = None,
        contractor_id: ContractorEntityId | None = None,
    ) -> list[DocumentDTO]:
        documents = await self._documents.list(
            limit=limit,
            offset=offset,
            status=status,
            contractor_entity_id=contractor_id,
        )
        return [document_to_dto(document) for document in documents]


__all__ = ["ListDocumentsUseCase"]
