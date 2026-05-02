from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.features.ingest.entities.document import Document, DocumentStatus


@dataclass(frozen=True)
class DocumentDTO:
    id: DocumentId
    title: str
    status: DocumentStatus
    doc_type: str | None
    document_kind: str | None
    contractor_entity_id: ContractorEntityId | None
    content_type: str
    partial_extraction: bool
    error_message: str | None
    created_at: datetime


@dataclass(frozen=True)
class DocumentFactsDTO:
    fields: dict[str, Any]
    summary: str | None
    key_points: list[str]
    partial_extraction: bool


def document_to_dto(document: Document) -> DocumentDTO:
    return DocumentDTO(
        id=document.id,
        title=document.title,
        status=document.status,
        doc_type=document.doc_type,
        document_kind=document.document_kind,
        contractor_entity_id=document.contractor_entity_id,
        content_type=document.content_type,
        partial_extraction=document.partial_extraction,
        error_message=document.error_message,
        created_at=document.created_at,
    )


__all__ = ["DocumentDTO", "DocumentFactsDTO", "document_to_dto"]
