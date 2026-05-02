from __future__ import annotations

from typing import Protocol, runtime_checkable

from sage import ContractFields

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.ingest.entities.document import Document, DocumentStatus
from app.features.ingest.ports import (
    DocumentNotFound,
    DocumentRepository,
    FieldsRepository,
    SummaryRepository,
)


@runtime_checkable
class DocumentReader(Protocol):
    async def get(self, document_id: DocumentId) -> Document: ...


@runtime_checkable
class DocumentListReader(Protocol):
    async def list(
        self,
        *,
        limit: int,
        offset: int,
        status: DocumentStatus | None = None,
        contractor_entity_id: ContractorEntityId | None = None,
    ) -> list[Document]: ...


@runtime_checkable
class FieldsReader(Protocol):
    async def get(self, document_id: DocumentId) -> ContractFields | None: ...


@runtime_checkable
class SummaryReader(Protocol):
    async def get(self, document_id: DocumentId) -> tuple[str, list[str]] | None: ...


__all__ = [
    "DocumentNotFound",
    "DocumentListReader",
    "DocumentReader",
    "DocumentRepository",
    "FieldsReader",
    "FieldsRepository",
    "SummaryReader",
    "SummaryRepository",
]
