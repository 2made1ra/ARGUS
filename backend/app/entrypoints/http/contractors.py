from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.entrypoints.http.dependencies import (
    get_contractor_profile_uc,
    get_list_contractor_documents_uc,
    get_search_documents_uc,
)
from app.entrypoints.http.documents import DocumentOut
from app.features.contractors.ports import ContractorNotFound
from app.features.contractors.use_cases.get_contractor_profile import (
    ContractorProfile,
    GetContractorProfileUseCase,
)
from app.features.contractors.use_cases.list_contractor_documents import (
    ListContractorDocumentsUseCase,
)
from app.features.documents.dto import document_to_dto
from app.features.search.dto import ChunkSnippet, DocumentSearchResult
from app.features.search.use_cases.search_documents import SearchDocumentsUseCase

router = APIRouter(prefix="/contractors", tags=["contractors"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ContractorOut(BaseModel):
    id: UUID
    display_name: str
    normalized_key: str
    inn: str | None
    kpp: str | None
    created_at: datetime


class ContractorProfileOut(BaseModel):
    contractor: ContractorOut
    document_count: int
    raw_mapping_count: int

    @classmethod
    def from_domain(cls, profile: ContractorProfile) -> "ContractorProfileOut":
        c = profile.contractor
        return cls(
            contractor=ContractorOut(
                id=UUID(str(c.id)),
                display_name=c.display_name,
                normalized_key=c.normalized_key,
                inn=c.inn,
                kpp=c.kpp,
                created_at=c.created_at,
            ),
            document_count=profile.document_count,
            raw_mapping_count=profile.raw_mapping_count,
        )


class ChunkSnippetOut(BaseModel):
    page: int | None
    snippet: str
    score: float


class DocumentSearchResultOut(BaseModel):
    document_id: UUID
    title: str
    date: str | None
    matched_chunks: list[ChunkSnippetOut]

    @classmethod
    def from_domain(cls, r: DocumentSearchResult) -> "DocumentSearchResultOut":
        return cls(
            document_id=UUID(str(r.document_id)),
            title=r.title,
            date=r.date,
            matched_chunks=[
                ChunkSnippetOut(page=c.page, snippet=c.snippet, score=c.score)
                for c in r.matched_chunks
            ],
        )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


@router.get("/{id}", response_model=ContractorProfileOut)
async def get_contractor(
    id: UUID,
    uc: GetContractorProfileUseCase = Depends(get_contractor_profile_uc),
) -> ContractorProfileOut:
    try:
        profile = await uc.execute(ContractorEntityId(id))
    except ContractorNotFound:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return ContractorProfileOut.from_domain(profile)


@router.get("/{id}/documents", response_model=list[DocumentOut])
async def list_contractor_documents(
    id: UUID,
    limit: int = 20,
    offset: int = 0,
    uc: ListContractorDocumentsUseCase = Depends(get_list_contractor_documents_uc),
) -> list[DocumentOut]:
    docs = await uc.execute(
        contractor_id=ContractorEntityId(id),
        limit=limit,
        offset=offset,
    )
    return [DocumentOut.from_dto(document_to_dto(doc)) for doc in docs]


@router.get("/{id}/search", response_model=list[DocumentSearchResultOut])
async def search_contractor_documents(
    id: UUID,
    q: str,
    limit: int = 20,
    uc: SearchDocumentsUseCase = Depends(get_search_documents_uc),
) -> list[DocumentSearchResultOut]:
    results = await uc.execute(
        contractor_entity_id=ContractorEntityId(id),
        query=q,
        limit=limit,
    )
    return [DocumentSearchResultOut.from_domain(r) for r in results]


__all__ = [
    "ContractorOut",
    "ContractorProfileOut",
    "DocumentSearchResultOut",
    "router",
]
