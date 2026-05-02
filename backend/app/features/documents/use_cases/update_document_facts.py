from __future__ import annotations

from typing import Protocol

from sage import ContractFields

from app.core.domain.ids import DocumentId
from app.features.ingest.ports import FieldsRepository, SummaryRepository


class _UoW(Protocol):
    async def commit(self) -> None: ...


class UpdateDocumentFactsUseCase:
    def __init__(
        self,
        *,
        fields: FieldsRepository,
        summaries: SummaryRepository,
        uow: _UoW,
    ) -> None:
        self._fields = fields
        self._summaries = summaries
        self._uow = uow

    async def execute(
        self,
        document_id: DocumentId,
        *,
        fields: ContractFields,
        summary: str | None,
        key_points: list[str],
    ) -> None:
        await self._fields.upsert(document_id, fields)
        if summary is not None:
            await self._summaries.upsert(document_id, summary, key_points)
        await self._uow.commit()


__all__ = ["UpdateDocumentFactsUseCase"]
