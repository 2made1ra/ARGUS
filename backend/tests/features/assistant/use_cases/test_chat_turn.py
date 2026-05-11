from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.features.assistant.dto import (
    AssistantChatRequest,
    BriefState,
    FoundCatalogItem,
    MatchReason,
    RouterDecision,
)
from app.features.assistant.use_cases.chat_turn import ChatTurnUseCase


class FakeRouter:
    def __init__(self, decision: RouterDecision) -> None:
        self.decision = decision
        self.calls: list[dict[str, Any]] = []

    async def route(self, *, message: str, brief: BriefState) -> RouterDecision:
        self.calls.append({"message": message, "brief": brief})
        return self.decision


class FakeCatalogSearchTool:
    def __init__(self, items: list[FoundCatalogItem] | None = None) -> None:
        self.items = items if items is not None else []
        self.calls: list[dict[str, Any]] = []

    async def search_items(self, *, query: str, limit: int) -> list[FoundCatalogItem]:
        self.calls.append({"query": query, "limit": limit})
        return self.items


def _decision(
    *,
    intent: str,
    should_search_now: bool,
    search_query: str | None = None,
    brief_update: BriefState | None = None,
    missing_fields: list[str] | None = None,
) -> RouterDecision:
    return RouterDecision(
        intent=intent,
        confidence=0.88,
        known_facts={},
        missing_fields=missing_fields if missing_fields is not None else [],
        should_search_now=should_search_now,
        search_query=search_query,
        brief_update=brief_update if brief_update is not None else BriefState(),
    )


def _found_item() -> FoundCatalogItem:
    return FoundCatalogItem(
        id=uuid4(),
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
    )


@pytest.mark.asyncio
async def test_brief_discovery_updates_brief_without_search() -> None:
    router = FakeRouter(
        _decision(
            intent="brief_discovery",
            should_search_now=False,
            brief_update=BriefState(event_type="музыкальный вечер"),
            missing_fields=["city", "audience_size", "venue_status"],
        ),
    )
    search = FakeCatalogSearchTool()
    use_case = ChatTurnUseCase(router=router, catalog_search=search)

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="Хочу музыкальный вечер",
            brief=BriefState(),
        ),
    )

    assert response.session_id is not None
    assert response.router.intent == "brief_discovery"
    assert response.brief.event_type == "музыкальный вечер"
    assert response.found_items == []
    assert search.calls == []
    assert "уточ" in response.message.lower()


@pytest.mark.asyncio
async def test_supplier_search_calls_search_items_and_returns_found_items() -> None:
    found = _found_item()
    router = FakeRouter(
        _decision(
            intent="supplier_search",
            should_search_now=True,
            search_query="музыкальное оборудование",
        ),
    )
    search = FakeCatalogSearchTool(items=[found])
    use_case = ChatTurnUseCase(router=router, catalog_search=search)

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=uuid4(),
            message="Нужно музыкальное оборудование",
            brief=BriefState(),
        ),
    )

    assert search.calls == [{"query": "музыкальное оборудование", "limit": 10}]
    assert response.router.intent == "supplier_search"
    assert response.found_items == [found]
    assert "found_items" in response.message
    assert "кандидат" in response.message.lower()


@pytest.mark.asyncio
async def test_mixed_updates_brief_and_returns_cards_when_search_runs() -> None:
    found = _found_item()
    router = FakeRouter(
        _decision(
            intent="mixed",
            should_search_now=True,
            search_query="звук для музыкального вечера на 100 человек",
            brief_update=BriefState(
                event_type="музыкальный вечер",
                audience_size=100,
                required_services=["звук"],
            ),
        ),
    )
    search = FakeCatalogSearchTool(items=[found])
    use_case = ChatTurnUseCase(router=router, catalog_search=search)

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="Организовать музыкальный вечер на 100 человек",
            brief=BriefState(city="Москва"),
        ),
    )

    assert response.router.intent == "mixed"
    assert response.brief.event_type == "музыкальный вечер"
    assert response.brief.city == "Москва"
    assert response.brief.audience_size == 100
    assert response.brief.required_services == ["звук"]
    assert response.found_items == [found]


@pytest.mark.asyncio
async def test_supplier_search_is_not_prose_only() -> None:
    found = _found_item()
    router = FakeRouter(
        _decision(
            intent="supplier_search",
            should_search_now=True,
            search_query="световое оборудование",
        ),
    )
    use_case = ChatTurnUseCase(
        router=router,
        catalog_search=FakeCatalogSearchTool(items=[found]),
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="Нужно световое оборудование",
            brief=BriefState(),
        ),
    )

    assert response.found_items == [found]
    assert response.message != "Я нашел варианты."


@pytest.mark.asyncio
async def test_message_does_not_claim_catalog_facts_from_found_items() -> None:
    found = _found_item()
    router = FakeRouter(
        _decision(
            intent="supplier_search",
            should_search_now=True,
            search_query="акустика на 15 мая",
        ),
    )
    use_case = ChatTurnUseCase(
        router=router,
        catalog_search=FakeCatalogSearchTool(items=[found]),
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="Нужна акустика на 15 мая",
            brief=BriefState(),
        ),
    )

    forbidden_fragments = [
        "15000",
        "ООО НИКА",
        "Москва",
        "день",
        "7701234567",
        "+7",
        "@",
        "15 мая есть",
    ]
    assert all(fragment not in response.message for fragment in forbidden_fragments)
    assert response.found_items == [found]


@pytest.mark.asyncio
async def test_empty_result_says_catalog_has_no_matching_rows() -> None:
    router = FakeRouter(
        _decision(
            intent="supplier_search",
            should_search_now=True,
            search_query="неизвестная услуга",
        ),
    )
    use_case = ChatTurnUseCase(
        router=router,
        catalog_search=FakeCatalogSearchTool(items=[]),
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="Нужна неизвестная услуга",
            brief=BriefState(),
        ),
    )

    assert response.found_items == []
    assert "В каталоге нет строк" in response.message
    assert "уточ" in response.message.lower()


@pytest.mark.asyncio
async def test_clarification_asks_follow_up_without_search() -> None:
    router = FakeRouter(
        _decision(
            intent="clarification",
            should_search_now=False,
            missing_fields=["event_type"],
        ),
    )
    search = FakeCatalogSearchTool()
    use_case = ChatTurnUseCase(router=router, catalog_search=search)

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=UUID("11111111-1111-1111-1111-111111111111"),
            message="подскажи",
            brief=BriefState(),
        ),
    )

    assert response.session_id == UUID("11111111-1111-1111-1111-111111111111")
    assert response.router.intent == "clarification"
    assert response.found_items == []
    assert search.calls == []
    assert "уточ" in response.message.lower()
