from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.core.domain.ids import ContractorEntityId, DocumentId
from app.entrypoints.http.dependencies import (
    get_contractor_rag_answer_uc,
    get_contractor_profile_uc,
    get_list_contractors_uc,
    get_list_contractor_documents_uc,
    get_search_documents_uc,
)
from app.entrypoints.http.schemas.contractors import (
    ContractorCatalogItemOut,
    ContractorProfileOut,
    DocumentSearchResultOut,
)
from app.entrypoints.http.schemas.documents import DocumentOut
from app.entrypoints.http.schemas.rag import RagAnswerOut, RagAnswerRequest
from app.features.contractors.ports import ContractorNotFound
from app.features.contractors.use_cases.get_contractor_profile import (
    GetContractorProfileUseCase,
)
from app.features.contractors.use_cases.list_contractors import ListContractorsUseCase
from app.features.contractors.use_cases.list_contractor_documents import (
    ListContractorDocumentsUseCase,
)
from app.features.documents.dto import document_to_dto
from app.features.search.use_cases.answer_contractor import AnswerContractorUseCase
from app.features.search.use_cases.search_documents import SearchDocumentsUseCase

router = APIRouter(prefix="/contractors", tags=["contractors"])


@router.get("/", response_model=list[ContractorCatalogItemOut])
async def list_contractors(
    limit: int = 50,
    offset: int = 0,
    q: str | None = None,
    uc: ListContractorsUseCase = Depends(get_list_contractors_uc),
) -> list[ContractorCatalogItemOut]:
    items = await uc.execute(limit=limit, offset=offset, q=q)
    return [ContractorCatalogItemOut.from_domain(item) for item in items]


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


@router.post("/{id}/answer", response_model=RagAnswerOut)
async def answer_contractor(
    id: UUID,
    body: RagAnswerRequest,
    uc: AnswerContractorUseCase = Depends(get_contractor_rag_answer_uc),
) -> RagAnswerOut:
    try:
        answer = await uc.execute(
            contractor_id=ContractorEntityId(id),
            message=body.message,
            history=[item.to_domain() for item in body.history],
        )
    except ContractorNotFound:
        raise HTTPException(status_code=404, detail="Contractor not found")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 503:
            raise HTTPException(
                status_code=503,
                detail="Сервис локальной LLM недоступен — запустите LM Studio и загрузите модель.",
            ) from exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RagAnswerOut.from_domain(answer)


__all__ = ["router"]
