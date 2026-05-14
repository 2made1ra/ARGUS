from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.features.assistant.domain.brief_renderer import BriefRenderer
from app.features.assistant.domain.tool_executor import ToolExecutor
from app.features.assistant.dto import (
    AssistantChatRequest,
    AssistantInterfaceMode,
    BriefState,
    CatalogItemDetail,
    CatalogSearchFilters,
    EventBriefWorkflowState,
    FoundCatalogItem,
    MatchReason,
    RenderedEventBrief,
    SupplierVerificationResult,
    VisibleCandidate,
)
from app.features.assistant.router import HeuristicAssistantRouter
from app.features.assistant.use_cases.chat_turn import ChatTurnUseCase


class FakeCatalogSearchTool:
    def __init__(self, items: list[FoundCatalogItem] | None = None) -> None:
        self.items = items if items is not None else []
        self.calls: list[dict[str, Any]] = []

    async def search_items(
        self,
        *,
        query: str,
        limit: int,
        filters: CatalogSearchFilters | None = None,
    ) -> list[FoundCatalogItem]:
        self.calls.append({"query": query, "limit": limit, "filters": filters})
        return self.items


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


@pytest.mark.asyncio
async def test_ux7_intake_case_opens_brief_workspace_without_catalog_search() -> None:
    search = FakeCatalogSearchTool()
    use_case = ChatTurnUseCase(
        router=HeuristicAssistantRouter(),
        catalog_search=search,
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="Нужно организовать корпоратив на 120 человек в Екатеринбурге.",
            brief=BriefState(),
        ),
    )

    assert response.ui_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert response.router.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert response.action_plan is not None
    assert response.action_plan.workflow_stage == EventBriefWorkflowState.CLARIFYING
    assert response.action_plan.tool_intents == ["update_brief"]
    assert "search_items" not in response.action_plan.tool_intents
    assert response.brief.event_type == "корпоратив"
    assert response.brief.city == "Екатеринбург"
    assert response.brief.audience_size == 120
    assert response.found_items == []
    assert search.calls == []
    assert {"date_or_period", "venue_status", "budget_total"} <= set(
        response.action_plan.missing_fields,
    )


@pytest.mark.asyncio
async def test_ux7_direct_search_case_stays_chat_search_with_inline_candidates(
) -> None:
    found = _found_item(name="Световой комплект", category="Свет")
    search = FakeCatalogSearchTool(items=[found])
    use_case = ChatTurnUseCase(
        router=HeuristicAssistantRouter(),
        catalog_search=search,
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="Найди подрядчика по свету в Екатеринбурге.",
            brief=BriefState(),
        ),
    )

    assert response.ui_mode == AssistantInterfaceMode.CHAT_SEARCH
    assert response.action_plan is not None
    assert response.action_plan.workflow_stage == EventBriefWorkflowState.SEARCHING
    assert response.action_plan.search_requests[0].service_category == "свет"
    assert response.action_plan.search_requests[0].filters.supplier_city_normalized == (
        "екатеринбург"
    )
    assert "date_or_period" not in response.action_plan.missing_fields
    assert "venue_status" not in response.action_plan.missing_fields
    assert response.brief.event_type is None
    assert response.brief.selected_item_ids == []
    assert [item.id for item in response.found_items] == [found.id]
    assert response.found_items[0].matched_service_categories == ["свет"]
    assert search.calls
    assert "обновил бриф" not in response.message.lower()


@pytest.mark.asyncio
async def test_ux7_direct_search_with_active_brief_stays_chat_search() -> None:
    found = _found_item(name="Фуршет на 120 гостей", category="Кейтеринг")
    search = FakeCatalogSearchTool(items=[found])
    use_case = ChatTurnUseCase(
        router=HeuristicAssistantRouter(),
        catalog_search=search,
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="На 120 человек в Екатеринбурге нужен кейтеринг до 2500 на гостя.",
            brief=BriefState(event_type="корпоратив", city="Екатеринбург"),
        ),
    )

    assert response.ui_mode == AssistantInterfaceMode.CHAT_SEARCH
    assert response.router.intent == "supplier_search"
    assert response.action_plan is not None
    assert response.action_plan.workflow_stage == (
        EventBriefWorkflowState.SEARCHING
    )
    assert response.action_plan.tool_intents == ["search_items"]
    assert response.brief.event_type == "корпоратив"
    assert response.brief.city == "Екатеринбург"
    assert response.brief.budget_per_guest is None
    assert response.brief.audience_size is None
    assert response.brief.required_services == []
    assert response.action_plan.search_requests[0].service_category == "кейтеринг"
    assert response.action_plan.search_requests[0].filters.supplier_city_normalized == (
        "екатеринбург"
    )
    assert response.action_plan.search_requests[0].filters.unit_price_max == 2500
    assert [item.id for item in response.found_items] == [found.id]
    assert response.found_items[0].matched_service_categories == ["кейтеринг"]


@pytest.mark.asyncio
async def test_ux7_venue_constraint_case_updates_brief_and_runs_requested_search(
) -> None:
    found = _found_item(name="Ground support ферма", category="Сцена")
    search = FakeCatalogSearchTool(items=[found])
    use_case = ChatTurnUseCase(
        router=HeuristicAssistantRouter(),
        catalog_search=search,
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="Добавь, что площадка без подвеса, и посмотри фермы.",
            brief=BriefState(
                event_type="корпоратив",
                city="Екатеринбург",
                audience_size=120,
            ),
        ),
    )

    assert response.ui_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert response.action_plan is not None
    assert response.action_plan.workflow_stage == (
        EventBriefWorkflowState.SUPPLIER_SEARCHING
    )
    assert response.action_plan.tool_intents == ["update_brief", "search_items"]
    assert response.brief.venue_constraints == ["площадка без подвеса"]
    assert response.action_plan.search_requests[0].service_category == (
        "сценические конструкции"
    )
    assert [item.id for item in response.found_items] == [found.id]
    assert response.found_items[0].matched_service_categories == [
        "сценические конструкции",
    ]
    assert search.calls
    assert "сможет" not in response.message.lower()
    assert "доступен" not in response.message.lower()
    assert "доступна на дату" not in response.message.lower()


@pytest.mark.asyncio
async def test_ux7_venue_constraint_without_search_inferrs_planning_only() -> None:
    search = FakeCatalogSearchTool()
    use_case = ChatTurnUseCase(
        router=HeuristicAssistantRouter(),
        catalog_search=search,
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="Площадка без подвеса, нужен корпоратив на 300 человек.",
            brief=BriefState(),
        ),
    )

    inferred_categories = {
        need.category
        for need in response.brief.service_needs
        if need.source == "policy_inferred"
    }
    assert response.ui_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert response.action_plan is not None
    assert response.action_plan.tool_intents == ["update_brief"]
    assert "search_items" not in response.action_plan.tool_intents
    assert response.brief.venue_constraints == ["площадка без подвеса"]
    assert inferred_categories == {"сценические конструкции", "свет", "мультимедиа"}
    assert response.found_items == []
    assert search.calls == []


@pytest.mark.asyncio
async def test_ux7_selection_case_requires_visible_candidates_for_ordinal() -> None:
    first_id = UUID("11111111-1111-1111-1111-111111111111")
    second_id = UUID("22222222-2222-2222-2222-222222222222")
    use_case = ChatTurnUseCase(
        router=HeuristicAssistantRouter(),
        catalog_search=FakeCatalogSearchTool(),
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="Добавь в подборку второй вариант.",
            brief=BriefState(event_type="корпоратив"),
            visible_candidates=[
                VisibleCandidate(ordinal=1, item_id=first_id, service_category="свет"),
                VisibleCandidate(
                    ordinal=2,
                    item_id=second_id,
                    service_category="свет",
                ),
            ],
        ),
    )

    assert response.ui_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert response.router.intent == "selection"
    assert response.action_plan is not None
    assert response.action_plan.tool_intents == ["select_item"]
    assert response.brief.selected_item_ids == [second_id]
    assert response.found_items == []

    clarification = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="Добавь в подборку второй вариант.",
            brief=BriefState(event_type="корпоратив"),
        ),
    )

    assert clarification.router.intent == "selection"
    assert clarification.action_plan is not None
    assert clarification.action_plan.tool_intents == []
    assert clarification.action_plan.missing_fields == ["candidate_context"]
    assert clarification.brief.selected_item_ids == []


@pytest.mark.asyncio
async def test_ux7_selection_does_not_treat_generic_priority_as_ordinal() -> None:
    first_id = UUID("11111111-1111-1111-1111-111111111111")
    second_id = UUID("22222222-2222-2222-2222-222222222222")
    use_case = ChatTurnUseCase(
        router=HeuristicAssistantRouter(),
        catalog_search=FakeCatalogSearchTool(),
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="Добавь в подборку в первую очередь кейтеринг.",
            brief=BriefState(event_type="корпоратив"),
            visible_candidates=[
                VisibleCandidate(ordinal=1, item_id=first_id, service_category="свет"),
                VisibleCandidate(
                    ordinal=2,
                    item_id=second_id,
                    service_category="кейтеринг",
                ),
            ],
        ),
    )

    assert response.router.intent == "selection"
    assert response.action_plan is not None
    assert response.action_plan.tool_intents == []
    assert response.action_plan.missing_fields == ["candidate_context"]
    assert response.brief.selected_item_ids == []


@pytest.mark.asyncio
async def test_ux7_verification_case_keeps_results_separate_from_prose() -> None:
    first_id = UUID("33333333-3333-3333-3333-333333333331")
    duplicate_inn_id = UUID("33333333-3333-3333-3333-333333333332")
    missing_inn_id = UUID("33333333-3333-3333-3333-333333333333")
    details = FakeCatalogItemDetailsTool(
        {
            first_id: _item_detail(first_id, supplier="ООО Свет", supplier_inn="7701"),
            duplicate_inn_id: _item_detail(
                duplicate_inn_id,
                supplier="ООО Свет",
                supplier_inn="7701",
            ),
            missing_inn_id: _item_detail(
                missing_inn_id,
                supplier="ИП Без ИНН",
                supplier_inn=None,
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
            message="Проверь найденных подрядчиков.",
            brief=BriefState(event_type="корпоратив"),
            candidate_item_ids=[first_id, duplicate_inn_id, missing_inn_id],
        ),
    )

    assert response.action_plan is not None
    assert response.action_plan.tool_intents == ["verify_supplier_status"]
    assert verifier.calls == [
        {"inn": "7701", "ogrn": None, "supplier_name": "ООО Свет"},
    ]
    assert [result.item_id for result in response.verification_results] == [
        first_id,
        duplicate_inn_id,
        missing_inn_id,
    ]
    assert [result.status for result in response.verification_results] == [
        "active",
        "active",
        "not_verified",
    ]
    assert response.verification_results[2].risk_flags == ["supplier_inn_missing"]
    assert "verification_results" in response.message
    assert "доступен" not in response.message.lower()
    assert "доступна на дату" not in response.message.lower()
    assert "рекоменд" not in response.message.lower()
    assert "действующий договор" not in response.message.lower()


@pytest.mark.asyncio
async def test_ux7_verification_without_context_asks_for_candidates() -> None:
    details = FakeCatalogItemDetailsTool({})
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
            message="Проверь найденных подрядчиков.",
            brief=BriefState(),
            candidate_item_ids=[],
            visible_candidates=[],
        ),
    )

    assert response.action_plan is not None
    assert "verify_supplier_status" not in response.action_plan.tool_intents
    assert response.action_plan.missing_fields == ["candidate_context"]
    assert response.verification_results == []
    assert details.calls == []
    assert verifier.calls == []
    assert "каких" in response.message.lower()
    assert "active" not in response.message.lower()


def test_ux7_render_brief_case_labels_found_items_as_unselected_candidates() -> None:
    selected_id = UUID("44444444-4444-4444-4444-444444444441")
    found_only = _found_item(
        item_id=UUID("44444444-4444-4444-4444-444444444442"),
        name="Фуршет",
        category="Кейтеринг",
    )

    rendered = BriefRenderer().render(
        brief=BriefState(
            event_type="корпоратив",
            city="Екатеринбург",
            required_services=["кейтеринг"],
            open_questions=["date_or_period"],
            selected_item_ids=[],
            budget_per_guest=2500,
        ),
        selected_items=[],
        found_items=[found_only],
        verification_results=[
            SupplierVerificationResult(
                item_id=selected_id,
                supplier_name="ООО Свет",
                supplier_inn="7701",
                ogrn=None,
                legal_name=None,
                status="active",
                source="fake_registry",
                checked_at=None,
                risk_flags=[],
                message=None,
            ),
        ],
    )

    assert isinstance(rendered, RenderedEventBrief)
    assert _section_titles(rendered) == [
        "Основная информация",
        "Концепция и уровень",
        "Площадка и ограничения",
        "Блоки услуг",
        "Подборка кандидатов",
        "Проверка подрядчиков",
        "Бюджетные заметки",
        "Открытые вопросы",
    ]
    candidate_section = _section_items(rendered, "Подборка кандидатов")
    budget_section = _section_items(rendered, "Бюджетные заметки")
    assert any("Кандидаты найдены, но не выбраны" in item for item in candidate_section)
    assert all("Выбрано:" not in item for item in candidate_section)
    assert rendered.evidence["selected_item_ids"] == []
    assert rendered.evidence["verification_result_ids"] == [str(selected_id)]
    assert all("2500.00" not in item for item in budget_section)
    assert any("без выбранных позиций и количеств" in item for item in budget_section)
    assert "Дата или период мероприятия" in rendered.open_questions


def _found_item(
    *,
    item_id: UUID | None = None,
    name: str,
    category: str | None,
) -> FoundCatalogItem:
    return FoundCatalogItem(
        id=item_id or uuid4(),
        score=0.82,
        name=name,
        category=category,
        unit="день",
        unit_price=Decimal("15000.00"),
        supplier="ООО Тест",
        supplier_city="Екатеринбург",
        source_text_snippet=f"{name} из строки прайса",
        source_text_full_available=True,
        match_reason=MatchReason(
            code="semantic",
            label="Семантическое совпадение с запросом",
        ),
    )


def _item_detail(
    item_id: UUID,
    *,
    supplier: str,
    supplier_inn: str | None,
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


def _section_titles(rendered: RenderedEventBrief) -> list[str]:
    return [section.title for section in rendered.sections]


def _section_items(rendered: RenderedEventBrief, title: str) -> list[str]:
    for section in rendered.sections:
        if section.title == title:
            return section.items
    pytest.fail(f"section not found: {title}")
