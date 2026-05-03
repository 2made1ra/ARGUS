from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.features.contractors.use_cases.list_contractors import ContractorCatalogItem
from app.features.contractors.use_cases.get_contractor_profile import ContractorProfile
from app.features.search.dto import ChunkSnippet, DocumentSearchResult


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


class ContractorCatalogItemOut(BaseModel):
    id: UUID
    display_name: str
    normalized_key: str
    inn: str | None
    kpp: str | None
    document_count: int

    @classmethod
    def from_domain(cls, item: ContractorCatalogItem) -> "ContractorCatalogItemOut":
        return cls(
            id=UUID(str(item.id)),
            display_name=item.display_name,
            normalized_key=item.normalized_key,
            inn=item.inn,
            kpp=item.kpp,
            document_count=item.document_count,
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


__all__ = [
    "ChunkSnippetOut",
    "ContractorCatalogItemOut",
    "ContractorOut",
    "ContractorProfileOut",
    "DocumentSearchResultOut",
]
