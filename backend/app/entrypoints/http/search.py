from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.entrypoints.http.dependencies import get_search_contractors_uc
from app.features.search.dto import ContractorSearchResult
from app.features.search.use_cases.search_contractors import SearchContractorsUseCase

router = APIRouter(tags=["search"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


@router.get("/search", response_model=list[ContractorSearchResultOut])
async def search_contractors(
    q: str,
    limit: int = 20,
    uc: SearchContractorsUseCase = Depends(get_search_contractors_uc),
) -> list[ContractorSearchResultOut]:
    results = await uc.execute(query=q, limit=limit)
    return [ContractorSearchResultOut.from_domain(r) for r in results]


__all__ = ["ContractorSearchResultOut", "router"]
