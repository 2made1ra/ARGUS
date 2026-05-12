from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

from app.entrypoints.http.dependencies import get_chat_turn_uc
from app.features.assistant.dto import (
    AssistantChatResponse,
    BriefState,
    FoundCatalogItem,
    MatchReason,
    RouterDecision,
)
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


async def test_post_assistant_chat_returns_layered_response(app: FastAPI) -> None:
    session_id = uuid4()
    item_id = uuid4()
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = AssistantChatResponse(
        session_id=session_id,
        message=(
            "Обновил черновик брифа и нашел кандидатов в каталоге. "
            "Конкретные строки смотрите в found_items."
        ),
        router=RouterDecision(
            intent="mixed",
            confidence=0.88,
            known_facts={"event_type": "музыкальный вечер", "audience_size": 100},
            missing_fields=["city", "venue_status"],
            should_search_now=True,
            search_query="звук для музыкального вечера на 100 человек",
            brief_update=BriefState(
                event_type="музыкальный вечер",
                audience_size=100,
                required_services=["звук"],
            ),
        ),
        brief=BriefState(
            event_type="музыкальный вечер",
            audience_size=100,
            required_services=["звук"],
        ),
        found_items=[
            FoundCatalogItem(
                id=item_id,
                score=0.82,
                name="Аренда акустической системы",
                category="Аренда",
                unit="день",
                unit_price=Decimal("15000.00"),
                supplier="ООО НИКА",
                supplier_city="г. Москва",
                source_text_snippet="Акустика 2 кВт",
                source_text_full_available=True,
                match_reason=MatchReason(
                    code="semantic",
                    label="Семантическое совпадение с запросом",
                ),
            ),
        ],
    )
    app.dependency_overrides[get_chat_turn_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/assistant/chat",
            json={
                "session_id": None,
                "message": "Организовать музыкальный вечер на 100 человек",
                "brief": {
                    "event_type": None,
                    "city": None,
                    "date_or_period": None,
                    "audience_size": None,
                    "venue": None,
                    "venue_status": None,
                    "duration_or_time_window": None,
                    "budget": None,
                    "event_level": None,
                    "required_services": [],
                    "constraints": [],
                    "preferences": [],
                },
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == str(session_id)
    assert set(body) == {
        "session_id",
        "message",
        "ui_mode",
        "router",
        "action_plan",
        "brief",
        "found_items",
        "verification_results",
        "rendered_brief",
    }
    assert body["ui_mode"] == "chat_search"
    assert body["router"]["intent"] == "mixed"
    assert body["router"]["interface_mode"] == "chat_search"
    assert body["brief"]["event_type"] == "музыкальный вечер"
    assert body["found_items"] == [
        {
            "id": str(item_id),
            "score": 0.82,
            "name": "Аренда акустической системы",
            "category": "Аренда",
            "unit": "день",
            "unit_price": "15000.00",
            "supplier": "ООО НИКА",
            "supplier_city": "г. Москва",
            "source_text_snippet": "Акустика 2 кВт",
            "source_text_full_available": True,
            "match_reason": {
                "code": "semantic",
                "label": "Семантическое совпадение с запросом",
            },
            "result_group": None,
            "matched_service_category": None,
            "matched_service_categories": [],
        },
    ]
    call_request = fake_uc.execute.await_args.args[0]
    assert call_request.session_id is None
    assert call_request.message == "Организовать музыкальный вечер на 100 человек"
    assert call_request.brief == BriefState()
