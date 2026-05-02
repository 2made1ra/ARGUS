from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.features.documents.dto import DocumentDTO, DocumentFactsDTO
from app.features.search.dto import WithinDocumentResult


class DocumentOut(BaseModel):
    id: UUID
    title: str
    status: str
    doc_type: str | None
    document_kind: str | None
    contractor_entity_id: UUID | None
    content_type: str
    partial_extraction: bool
    error_message: str | None
    created_at: datetime
    preview_available: bool

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_dto(cls, dto: DocumentDTO) -> "DocumentOut":
        return cls(
            id=UUID(str(dto.id)),
            title=dto.title,
            status=str(dto.status),
            doc_type=dto.doc_type,
            document_kind=dto.document_kind,
            contractor_entity_id=UUID(str(dto.contractor_entity_id))
            if dto.contractor_entity_id is not None
            else None,
            content_type=dto.content_type,
            partial_extraction=dto.partial_extraction,
            error_message=dto.error_message,
            created_at=dto.created_at,
            preview_available=dto.preview_available,
        )


class DocumentFactsOut(BaseModel):
    fields: dict[str, Any]
    summary: str | None
    key_points: list[str]
    partial_extraction: bool

    @classmethod
    def from_dto(cls, dto: DocumentFactsDTO) -> "DocumentFactsOut":
        return cls(
            fields=dto.fields,
            summary=dto.summary,
            key_points=dto.key_points,
            partial_extraction=dto.partial_extraction,
        )


class WithinDocumentResultOut(BaseModel):
    chunk_index: int
    page_start: int | None
    page_end: int | None
    section_type: str | None
    snippet: str
    score: float

    @classmethod
    def from_domain(cls, r: WithinDocumentResult) -> "WithinDocumentResultOut":
        return cls(
            chunk_index=r.chunk_index,
            page_start=r.page_start,
            page_end=r.page_end,
            section_type=r.section_type,
            snippet=r.snippet,
            score=r.score,
        )


class DocumentFactsPatch(BaseModel):
    fields: dict[str, Any] = {}
    summary: str | None = None
    key_points: list[str] = []


__all__ = ["DocumentFactsOut", "DocumentFactsPatch", "DocumentOut", "WithinDocumentResultOut"]
