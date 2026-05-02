from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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
    preview_available: bool


@dataclass(frozen=True)
class DocumentFactsDTO:
    fields: dict[str, Any]
    summary: str | None
    key_points: list[str]
    partial_extraction: bool


@dataclass(frozen=True)
class DocumentPreviewDTO:
    path: Path
    media_type: str


class DocumentPreviewUnavailable(Exception):
    def __init__(self, document_id: DocumentId) -> None:
        super().__init__(f"Document preview is unavailable: {document_id}")
        self.document_id = document_id


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
        preview_available=_preview_path(document) is not None,
    )


def _preview_path(document: Document) -> str | None:
    if document.preview_file_path:
        return document.preview_file_path
    if document.content_type == "application/pdf" or document.file_path.lower().endswith(
        ".pdf",
    ):
        return document.file_path
    return None


__all__ = [
    "DocumentDTO",
    "DocumentFactsDTO",
    "DocumentPreviewDTO",
    "DocumentPreviewUnavailable",
    "document_to_dto",
]
