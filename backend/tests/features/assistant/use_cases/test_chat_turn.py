from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.features.assistant.domain.tool_executor import ToolExecutor
from app.features.assistant.dto import (
    ActionPlan,
    AssistantChatRequest,
    AssistantInterfaceMode,
    BriefState,
    CatalogItemDetail,
    CatalogSearchFilters,
    ChatTurn,
    EventBriefWorkflowState,
    FoundCatalogItem,
    MatchReason,
    RouterDecision,
    SearchRequest,
    SupplierVerificationResult,
    ToolResults,
    VisibleCandidate,
)
from app.features.assistant.router import HeuristicAssistantRouter
from app.features.assistant.use_cases.chat_turn import ChatTurnUseCase


class FakeRouter:
    def __init__(self, decision: RouterDecision) -> None:
        self.decision = decision
        self.calls: list[dict[str, Any]] = []

    async def route(
        self,
        *,
        message: str,
        brief: BriefState,
        recent_turns: list[ChatTurn],
        visible_candidates: list[VisibleCandidate],
        candidate_item_ids: list[UUID],
    ) -> RouterDecision:
        self.calls.append(
            {
                "message": message,
                "brief": brief,
                "recent_turns": recent_turns,
                "visible_candidates": visible_candidates,
                "candidate_item_ids": candidate_item_ids,
            },
        )
        return self.decision


class FakeCatalogSearchTool:
    def __init__(
        self,
        items: list[FoundCatalogItem] | None = None,
        items_by_query: dict[str, list[FoundCatalogItem]] | None = None,
    ) -> None:
        self.items = items if items is not None else []
        self.items_by_query = items_by_query if items_by_query is not None else {}
        self.calls: list[dict[str, Any]] = []

    async def search_items(
        self,
        *,
        query: str,
        limit: int,
        filters: CatalogSearchFilters | None = None,
    ) -> list[FoundCatalogItem]:
        self.calls.append({"query": query, "limit": limit, "filters": filters})
        return self.items_by_query.get(query, self.items)


class FakeCatalogItemDetailsTool:
    def __init__(self, details: dict[UUID, CatalogItemDetail]) -> None:
        self.details = details
        self.calls: list[UUID] = []

    async def get_item_details(self, *, item_id: UUID) -> CatalogItemDetail | None:
        self.calls.append(item_id)
        return self.details.get(item_id)


class FakeSupplierVerificationPort:
    def __init__(self, *, status: str = "active") -> None:
        self.status = status
        self.calls: list[dict[str, str | None]] = []

    async def verify_by_inn_or_ogrn(
        self,
        *,
        inn: str | None,
        ogrn: str | None,
        supplier_name: str | None,
    ) -> SupplierVerificationResult:
        self.calls.append(
            {"inn": inn, "ogrn": ogrn, "supplier_name": supplier_name},
        )
        return SupplierVerificationResult(
            item_id=None,
            supplier_name=supplier_name,
            supplier_inn=inn,
            ogrn=ogrn,
            legal_name=supplier_name,
            status=self.status,
            source="fake_registry",
            checked_at=None,
            risk_flags=[],
            message=None,
        )


class FakeToolExecutor:
    def __init__(self) -> None:
        self.action_plans: list[ActionPlan] = []

    async def execute(
        self,
        *,
        action_plan: ActionPlan,
        brief: BriefState,
        brief_update: BriefState,
        message: str = "",
        recent_turns: list[ChatTurn] | None = None,
        visible_candidates: list[VisibleCandidate] | None = None,
        candidate_item_ids: list[UUID] | None = None,
    ) -> ToolResults:
        self.action_plans.append(action_plan)
        return ToolResults(brief=brief)


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


def _found_item(
    *,
    item_id: UUID | None = None,
    name: str = "Аренда акустической системы",
    category: str | None = "Аренда",
) -> FoundCatalogItem:
    return FoundCatalogItem(
        id=item_id or uuid4(),
        score=0.82,
        name=name,
        category=category,
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


def _item_detail(
    item_id: UUID,
    *,
    supplier: str = "ООО НИКА",
    supplier_inn: str | None = "7701234567",
) -> CatalogItemDetail:
    return CatalogItemDetail(
        id=item_id,
        name="Световой комплект",
        category="Свет",
        unit="день",
        unit_price=Decimal("15000.00"),
        supplier=supplier,
        supplier_inn=supplier_inn,
        supplier_city="Екатеринбург",
        supplier_phone=None,
        supplier_email=None,
        supplier_status=None,
        source_text="Световой комплект",
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
async def test_chat_turn_passes_explicit_context_to_router() -> None:
    router = FakeRouter(
        _decision(
            intent="clarification",
            should_search_now=False,
        ),
    )
    visible_candidate = VisibleCandidate(
        ordinal=1,
        item_id=UUID("11111111-1111-1111-1111-111111111111"),
        service_category="свет",
    )
    recent_turn = ChatTurn(role="user", content="Найди свет")
    use_case = ChatTurnUseCase(
        router=router,
        catalog_search=FakeCatalogSearchTool(),
    )

    await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="добавь второй",
            brief=BriefState(),
            recent_turns=[recent_turn],
            visible_candidates=[visible_candidate],
        ),
    )

    assert router.calls[0]["recent_turns"] == [recent_turn]
    assert router.calls[0]["visible_candidates"] == [visible_candidate]


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

    assert search.calls == [
        {
            "query": "музыкальное оборудование",
            "limit": 10,
            "filters": CatalogSearchFilters(),
        },
    ]
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
    assert [item.id for item in response.found_items] == [found.id]
    assert response.found_items[0].result_group == "звук"


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


@pytest.mark.asyncio
async def test_chat_turn_executes_policy_action_plan_without_reconstructing() -> None:
    item_id = UUID("22222222-2222-2222-2222-222222222222")
    policy_plan = ActionPlan(
        interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
        workflow_stage=EventBriefWorkflowState.SUPPLIER_VERIFICATION,
        tool_intents=["get_item_details", "verify_supplier_status"],
        item_detail_ids=[item_id],
        verification_targets=[item_id],
        render_requested=True,
    )
    router = FakeRouter(
        RouterDecision(
            intent="verification",
            confidence=0.9,
            known_facts={},
            missing_fields=[],
            should_search_now=False,
            search_query=None,
            brief_update=BriefState(),
            interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
            workflow_stage=EventBriefWorkflowState.SUPPLIER_VERIFICATION,
            tool_intents=["get_item_details", "verify_supplier_status"],
            action_plan=policy_plan,
        ),
    )
    executor = FakeToolExecutor()
    use_case = ChatTurnUseCase(router=router, tool_executor=executor)

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="проверь 22222222-2222-2222-2222-222222222222",
            brief=BriefState(),
        ),
    )

    assert executor.action_plans == [policy_plan]
    assert response.action_plan == policy_plan


@pytest.mark.asyncio
async def test_chat_turn_executes_grouped_searches_and_dedupes_found_items() -> None:
    shared_id = UUID("33333333-3333-3333-3333-333333333333")
    catering_id = UUID("44444444-4444-4444-4444-444444444444")
    light_id = UUID("55555555-5555-5555-5555-555555555555")
    shared = _found_item(
        item_id=shared_id,
        name="Комплект для события",
        category="Комплект",
    )
    catering = _found_item(
        item_id=catering_id,
        name="Фуршет на 120 гостей",
        category="Кейтеринг",
    )
    light = _found_item(
        item_id=light_id,
        name="Световой комплект",
        category="Свет",
    )
    search_requests = [
        SearchRequest(
            query="кейтеринг 120 человек Екатеринбург",
            service_category="кейтеринг",
            filters=CatalogSearchFilters(supplier_city_normalized="екатеринбург"),
            priority=1,
            limit=8,
        ),
        SearchRequest(
            query="свет 120 человек Екатеринбург",
            service_category="свет",
            filters=CatalogSearchFilters(supplier_city_normalized="екатеринбург"),
            priority=2,
            limit=8,
        ),
    ]
    action_plan = ActionPlan(
        interface_mode=AssistantInterfaceMode.CHAT_SEARCH,
        workflow_stage=EventBriefWorkflowState.SEARCHING,
        tool_intents=["search_items"],
        search_requests=search_requests,
    )
    router = FakeRouter(
        RouterDecision(
            intent="supplier_search",
            confidence=0.88,
            known_facts={},
            missing_fields=[],
            should_search_now=True,
            search_query="кейтеринг 120 человек Екатеринбург",
            brief_update=BriefState(),
            interface_mode=AssistantInterfaceMode.CHAT_SEARCH,
            workflow_stage=EventBriefWorkflowState.SEARCHING,
            search_requests=search_requests,
            tool_intents=["search_items"],
            action_plan=action_plan,
        ),
    )
    search = FakeCatalogSearchTool(
        items_by_query={
            "кейтеринг 120 человек Екатеринбург": [shared, catering],
            "свет 120 человек Екатеринбург": [shared, light],
        },
    )
    use_case = ChatTurnUseCase(router=router, catalog_search=search)

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="подбери кейтеринг и свет на 120 человек в Екатеринбурге",
            brief=BriefState(),
        ),
    )

    assert search.calls == [
        {
            "query": "кейтеринг 120 человек Екатеринбург",
            "limit": 8,
            "filters": CatalogSearchFilters(supplier_city_normalized="екатеринбург"),
        },
        {
            "query": "свет 120 человек Екатеринбург",
            "limit": 8,
            "filters": CatalogSearchFilters(supplier_city_normalized="екатеринбург"),
        },
    ]
    assert [item.id for item in response.found_items] == [
        shared_id,
        catering_id,
        light_id,
    ]
    assert response.found_items[0].result_group == "кейтеринг"
    assert response.found_items[0].matched_service_category == "кейтеринг"
    assert response.found_items[0].matched_service_categories == [
        "кейтеринг",
        "свет",
    ]
    assert response.found_items[2].result_group == "свет"


@pytest.mark.asyncio
async def test_chat_turn_plans_service_searches_for_catering_and_light_phrase() -> None:
    found = _found_item()
    search = FakeCatalogSearchTool(items=[found])
    use_case = ChatTurnUseCase(
        router=HeuristicAssistantRouter(),
        catalog_search=search,
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="подбери кейтеринг и свет на 120 человек в Екатеринбурге",
            brief=BriefState(),
        ),
    )

    assert response.action_plan is not None
    assert [
        request.service_category
        for request in response.action_plan.search_requests
    ] == ["кейтеринг", "свет"]
    assert len(search.calls) == 2
    assert all(
        call["filters"].supplier_city_normalized == "екатеринбург"
        for call in search.calls
    )
    assert response.found_items[0].result_group == "кейтеринг"
    assert response.found_items[0].matched_service_categories == [
        "кейтеринг",
        "свет",
    ]


@pytest.mark.asyncio
async def test_chat_turn_verifies_found_contractors_from_candidate_context() -> None:
    first_id = UUID("66666666-6666-6666-6666-666666666661")
    second_id = UUID("66666666-6666-6666-6666-666666666662")
    details = FakeCatalogItemDetailsTool(
        details={
            first_id: _item_detail(first_id, supplier="ООО НИКА"),
            second_id: _item_detail(second_id, supplier="ООО НИКА"),
        },
    )
    verifier = FakeSupplierVerificationPort(status="active")
    use_case = ChatTurnUseCase(
        router=HeuristicAssistantRouter(),
        tool_executor=ToolExecutor(
            catalog_search=None,
            item_details=details,
            supplier_verification=verifier,
        ),
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="проверь найденных подрядчиков",
            brief=BriefState(event_type="корпоратив"),
            candidate_item_ids=[first_id, second_id],
        ),
    )

    assert response.router.intent == "verification"
    assert response.action_plan is not None
    assert response.action_plan.tool_intents == ["verify_supplier_status"]
    assert response.action_plan.workflow_stage == (
        EventBriefWorkflowState.SUPPLIER_VERIFICATION
    )
    assert details.calls == [first_id, second_id]
    assert verifier.calls == [
        {"inn": "7701234567", "ogrn": None, "supplier_name": "ООО НИКА"},
    ]
    assert [result.item_id for result in response.verification_results] == [
        first_id,
        second_id,
    ]
    assert all(result.status == "active" for result in response.verification_results)
    forbidden_fragments = ["доступен", "рекоменду", "действующий договор"]
    assert all(
        fragment not in response.message.lower()
        for fragment in forbidden_fragments
    )


@pytest.mark.asyncio
async def test_chat_turn_verifies_explicit_item_id_without_candidate_context() -> None:
    item_id = UUID("77777777-7777-7777-7777-777777777771")
    details = FakeCatalogItemDetailsTool(
        details={
            item_id: _item_detail(
                item_id,
                supplier="ООО Точка",
                supplier_inn="1",
            ),
        },
    )
    verifier = FakeSupplierVerificationPort(status="active")
    use_case = ChatTurnUseCase(
        router=HeuristicAssistantRouter(),
        tool_executor=ToolExecutor(
            catalog_search=None,
            item_details=details,
            supplier_verification=verifier,
        ),
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message=f"проверь подрядчика {item_id}",
            brief=BriefState(),
        ),
    )

    assert response.action_plan is not None
    assert response.action_plan.verification_targets == [item_id]
    assert [result.item_id for result in response.verification_results] == [item_id]
    assert verifier.calls == [
        {"inn": "1", "ogrn": None, "supplier_name": "ООО Точка"},
    ]


@pytest.mark.asyncio
async def test_chat_turn_asks_clarification_without_candidate_context() -> None:
    details = FakeCatalogItemDetailsTool(details={})
    verifier = FakeSupplierVerificationPort()
    use_case = ChatTurnUseCase(
        router=HeuristicAssistantRouter(),
        tool_executor=ToolExecutor(
            catalog_search=None,
            item_details=details,
            supplier_verification=verifier,
        ),
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="проверь найденных подрядчиков",
            brief=BriefState(),
        ),
    )

    assert response.router.intent == "verification"
    assert response.action_plan is not None
    assert response.action_plan.tool_intents == []
    assert response.action_plan.missing_fields == ["candidate_context"]
    assert response.verification_results == []
    assert details.calls == []
    assert verifier.calls == []
    assert "каких" in response.message.lower()
