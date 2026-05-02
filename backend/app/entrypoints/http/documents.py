from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.entrypoints.http.dependencies import (
    get_document_facts_uc,
    get_get_document_uc,
    get_list_documents_uc,
    get_search_within_uc,
    get_upload_uc,
)
from app.features.documents.dto import DocumentDTO, DocumentFactsDTO
from app.features.documents.use_cases.get_document import GetDocumentUseCase
from app.features.documents.use_cases.get_document_facts import GetDocumentFactsUseCase
from app.features.documents.use_cases.list_documents import ListDocumentsUseCase
from app.features.ingest.entities.document import DocumentStatus
from app.features.ingest.ports import DocumentNotFound
from app.features.ingest.use_cases.upload_document import UploadDocumentUseCase
from app.features.search.dto import WithinDocumentResult
from app.features.search.use_cases.search_within_document import (
    SearchWithinDocumentUseCase,
)

router = APIRouter(prefix="/documents", tags=["documents"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


@router.post("/upload", status_code=202)
async def upload_document(
    file: UploadFile,
    content_type: str = Form(default=None),
    uc: UploadDocumentUseCase = Depends(get_upload_uc),
) -> dict[str, str]:
    ct = content_type or file.content_type or "application/octet-stream"
    try:
        doc_id = await uc.execute(
            file=file.file,
            filename=file.filename or "upload",
            content_type=ct,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"document_id": str(doc_id)}


@router.get("/", response_model=list[DocumentOut])
async def list_documents(
    limit: int = 50,
    offset: int = 0,
    status: DocumentStatus | None = None,
    contractor_id: UUID | None = None,
    uc: ListDocumentsUseCase = Depends(get_list_documents_uc),
) -> list[DocumentOut]:
    dtos = await uc.execute(
        limit=limit,
        offset=offset,
        status=status,
        contractor_id=ContractorEntityId(contractor_id) if contractor_id else None,
    )
    return [DocumentOut.from_dto(dto) for dto in dtos]


@router.get("/{id}/facts", response_model=DocumentFactsOut)
async def get_document_facts(
    id: UUID,
    uc: GetDocumentFactsUseCase = Depends(get_document_facts_uc),
) -> DocumentFactsOut:
    try:
        dto = await uc.execute(DocumentId(id))
    except DocumentNotFound:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentFactsOut.from_dto(dto)


@router.get("/{id}/search", response_model=list[WithinDocumentResultOut])
async def search_within_document(
    id: UUID,
    q: str,
    limit: int = 20,
    uc: SearchWithinDocumentUseCase = Depends(get_search_within_uc),
) -> list[WithinDocumentResultOut]:
    results = await uc.execute(document_id=DocumentId(id), query=q, limit=limit)
    return [WithinDocumentResultOut.from_domain(r) for r in results]


@router.get("/{id}", response_model=DocumentOut)
async def get_document(
    id: UUID,
    uc: GetDocumentUseCase = Depends(get_get_document_uc),
) -> DocumentOut:
    try:
        dto = await uc.execute(DocumentId(id))
    except DocumentNotFound:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentOut.from_dto(dto)


__all__ = ["DocumentFactsOut", "DocumentOut", "WithinDocumentResultOut", "router"]
