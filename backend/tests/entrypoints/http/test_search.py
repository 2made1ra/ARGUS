"""Smoke tests — GET /search handler."""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.domain.ids import ContractorEntityId
from app.entrypoints.http.dependencies import get_global_rag_answer_uc, get_search_contractors_uc
from app.features.search.dto import ContractorSearchResult, GlobalRagAnswer


async def test_search_contractors_returns_200(app: FastAPI) -> None:
    contractor_id = ContractorEntityId(uuid4())
    result = ContractorSearchResult(
        contractor_id=contractor_id,
        name="ООО Вектор",
        score=0.95,
        matched_chunks_count=3,
        top_snippet="supply of equipment",
    )
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = [result]
    app.dependency_overrides[get_search_contractors_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/search?q=equipment")

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert UUID(items[0]["contractor_id"]) == UUID(str(contractor_id))
    assert items[0]["name"] == "ООО Вектор"
    assert items[0]["top_snippet"] == "supply of equipment"


async def test_answer_global_search_returns_200(app: FastAPI) -> None:
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = GlobalRagAnswer(
        answer="Подходящих подрядчиков не найдено.",
        contractors=[],
        sources=[],
    )
    app.dependency_overrides[get_global_rag_answer_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/search/answer",
            json={"message": "мне нужны поставщики фруктов"},
        )

    assert resp.status_code == 200
    assert resp.json() == {
        "answer": "Подходящих подрядчиков не найдено.",
        "contractors": [],
        "sources": [],
    }
