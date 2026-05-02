from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.features.search.dto import ContractorSearchResult


class ContractorSearchResultOut(BaseModel):
    contractor_id: UUID
    name: str
    score: float
    matched_chunks_count: int
    top_snippet: str

    @classmethod
    def from_domain(cls, r: ContractorSearchResult) -> "ContractorSearchResultOut":
        return cls(
            contractor_id=UUID(str(r.contractor_id)),
            name=r.name,
            score=r.score,
            matched_chunks_count=r.matched_chunks_count,
            top_snippet=r.top_snippet,
        )


__all__ = ["ContractorSearchResultOut"]
