from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.entrypoints.http.dependencies import (
    get_global_rag_answer_uc,
    get_search_contractors_uc,
)
from app.entrypoints.http.schemas.rag import GlobalRagAnswerOut, RagAnswerRequest
from app.entrypoints.http.schemas.search import ContractorSearchResultOut
from app.features.search.use_cases.answer_global import AnswerGlobalSearchUseCase
from app.features.search.use_cases.search_contractors import SearchContractorsUseCase

router = APIRouter(tags=["search"])


@router.get(
    "/search",
    response_model=list[ContractorSearchResultOut],
    operation_id="searchContractors",
    summary="Search contractors",
    description=(
        "Runs global semantic search and aggregates matching chunks by contractor."
    ),
)
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
                detail=(
                    "Сервис эмбеддингов недоступен — запустите LM Studio "
                    "и загрузите модель эмбеддингов."
                ),
            ) from exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [ContractorSearchResultOut.from_domain(r) for r in results]


@router.post(
    "/search/answer",
    response_model=GlobalRagAnswerOut,
    operation_id="answerGlobalSearchQuestion",
    summary="Answer a global search question",
    description=(
        "Builds a RAG answer across all indexed documents and returns ranked "
        "contractors and sources."
    ),
)
async def answer_global_search(
    body: RagAnswerRequest,
    uc: AnswerGlobalSearchUseCase = Depends(get_global_rag_answer_uc),
) -> GlobalRagAnswerOut:
    try:
        answer = await uc.execute(
            message=body.message,
            history=[item.to_domain() for item in body.history],
            limit=body.limit,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 503:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Сервис локальной LLM недоступен — запустите LM Studio "
                    "и загрузите модель."
                ),
            ) from exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return GlobalRagAnswerOut.from_domain(answer)


__all__ = ["router"]
