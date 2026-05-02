from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

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
    try:
        results = await uc.execute(query=q, limit=limit)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 503:
            raise HTTPException(
                status_code=503,
                detail="Сервис эмбеддингов недоступен — запустите LM Studio и загрузите модель эмбеддингов.",
            ) from exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [ContractorSearchResultOut.from_domain(r) for r in results]


__all__ = ["router"]
