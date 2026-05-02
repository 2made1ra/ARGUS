from __future__ import annotations

from sage import ContractFields

from app.core.domain.ids import DocumentId
from app.features.documents.dto import DocumentFactsDTO
from app.features.documents.ports import (
    DocumentReader,
    FieldsReader,
    SummaryReader,
)


class GetDocumentFactsUseCase:
    def __init__(
        self,
        *,
        documents: DocumentReader,
        fields: FieldsReader,
        summaries: SummaryReader,
    ) -> None:
        self._documents = documents
        self._fields = fields
        self._summaries = summaries

    async def execute(self, document_id: DocumentId) -> DocumentFactsDTO:
        document = await self._documents.get(document_id)
        fields = await self._fields.get(document_id)
        summary = await self._summaries.get(document_id)

        summary_text: str | None
        key_points: list[str]
        if summary is None:
            summary_text = None
            key_points = []
        else:
            summary_text, key_points = summary

        return DocumentFactsDTO(
            fields=(fields or ContractFields()).model_dump(),
            summary=summary_text,
            key_points=key_points,
            partial_extraction=document.partial_extraction,
        )


__all__ = ["GetDocumentFactsUseCase"]
