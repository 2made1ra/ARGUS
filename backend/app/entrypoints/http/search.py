from __future__ import annotations

from fastapi import APIRouter, Depends

from app.entrypoints.http.dependencies import get_search_contractors_uc
from app.entrypoints.http.schemas.search import ContractorSearchResultOut
from app.features.search.use_cases.search_contractors import SearchContractorsUseCase

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[ContractorSearchResultOut])
async def search_contractors(
    q: str,
    limit: int = 20,
    uc: SearchContractorsUseCase = Depends(get_search_contractors_uc),
) -> list[ContractorSearchResultOut]:
    results = await uc.execute(query=q, limit=limit)
    return [ContractorSearchResultOut.from_domain(r) for r in results]


__all__ = ["router"]
