from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from app.features.assistant.brief import merge_brief
from app.features.assistant.domain.brief_workflow_policy import BriefWorkflowPolicy
from app.features.assistant.domain.event_brief_interpreter import EventBriefInterpreter
from app.features.assistant.domain.response_composer import ResponseComposer
from app.features.assistant.domain.tool_executor import ToolExecutor
from app.features.assistant.dto import (
    AssistantChatRequest,
    AssistantInterfaceMode,
    BriefState,
    CatalogItemDetail,
    EventBriefWorkflowState,
    FoundCatalogItem,
    RenderedBriefSection,
    RenderedEventBrief,
    RouterDecision,
)
from app.features.assistant.router import HeuristicAssistantRouter
from app.features.assistant.use_cases.chat_turn import ChatTurnUseCase


class FakeCatalogItemDetailsTool:
    def __init__(self, details: dict[UUID, CatalogItemDetail]) -> None:
        self.details = details
        self.calls: list[UUID] = []

    async def get_item_details(self, *, item_id: UUID) -> CatalogItemDetail | None:
        self.calls.append(item_id)
        return self.details.get(item_id)


def _detail(item_id: UUID) -> CatalogItemDetail:
    return CatalogItemDetail(
        id=item_id,
        name="Световой комплект",
        category="Свет",
        unit="день",
        unit_price=Decimal("15000.00"),
        supplier="ООО НИКА",
        supplier_inn="7701234567",
        supplier_city="Екатеринбург",
        supplier_phone=None,
        supplier_email=None,
        supplier_status=None,
        source_text="Световой комплект",
    )


def _compose(message: str, found_items: list[FoundCatalogItem] | None = None) -> str:
    brief = BriefState()
    interpretation = EventBriefInterpreter().interpret(message=message, brief=brief)
    plan = BriefWorkflowPolicy().plan(interpretation=interpretation, brief=brief)
    updated_brief = merge_brief(brief, interpretation.brief_update)
    return ResponseComposer().compose(
        interpretation=interpretation,
        action_plan=plan,
        brief=updated_brief,
        found_items=found_items if found_items is not None else [],
    )


def test_workspace_intake_asks_no_more_than_three_questions() -> None:
    message = _compose("Нужно организовать корпоратив на 120 человек в Екатеринбурге")

    assert "бриф" in message.lower()
    assert "корпоратив" in message
    assert "Екатеринбург" in message
    assert message.count("?") <= 3
    assert "дат" in message.lower()
    assert "площад" in message.lower()


def test_chat_search_does_not_claim_brief_workspace() -> None:
    message = _compose("найди подрядчика по свету в Екатеринбурге")

    assert "бриф" not in message.lower()
    assert "черновик" not in message.lower()
    assert "площадка уже есть" not in message.lower()
    assert "дату" not in message.lower()
    assert "каталог" in message.lower() or "подбор" in message.lower()


def test_rest_of_missing_fields_stay_in_brief_open_questions() -> None:
    current = BriefState(event_type="корпоратив", city="Екатеринбург")
    interpretation = EventBriefInterpreter().interpret(
        message="Нужно организовать корпоратив на 120 человек в Екатеринбурге",
        brief=BriefState(),
    )
    plan = BriefWorkflowPolicy().plan(interpretation=interpretation, brief=current)
    brief = merge_brief(current, interpretation.brief_update)

    assert len(plan.clarification_questions) <= 3
    assert "concept" in brief.open_questions
    assert plan.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE


def test_render_message_includes_structured_brief_in_chat() -> None:
    rendered = RenderedEventBrief(
        title="Бриф мероприятия",
        sections=[
            RenderedBriefSection(
                title="Основная информация",
                items=["Тип: корпоратив"],
            ),
        ],
        open_questions=["Дата или период мероприятия"],
        evidence={"selected_item_ids": [], "verification_result_ids": []},
    )
    message = ResponseComposer().compose_from_decision(
        decision=RouterDecision(
            intent="render_brief",
            confidence=0.9,
            known_facts={},
            missing_fields=[],
            should_search_now=False,
            search_query=None,
            brief_update=BriefState(),
            interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
            workflow_stage=EventBriefWorkflowState.BRIEF_RENDERED,
            tool_intents=["render_event_brief"],
        ),
        brief=BriefState(event_type="корпоратив"),
        found_items=[],
        rendered_brief=rendered,
    )

    assert "Бриф мероприятия" in message
    assert "Основная информация" in message
    assert "Тип: корпоратив" in message
    assert "Открытые вопросы" in message
    assert "Дата или период мероприятия" in message


def test_workspace_search_without_results_reports_empty_catalog_rows() -> None:
    message = ResponseComposer().compose_from_decision(
        decision=RouterDecision(
            intent="supplier_search",
            confidence=0.9,
            known_facts={},
            missing_fields=[],
            should_search_now=True,
            search_query="площадка музыкальный вечер",
            brief_update=BriefState(),
            interface_mode=AssistantInterfaceMode.BRIEF_WORKSPACE,
            workflow_stage=EventBriefWorkflowState.SUPPLIER_SEARCHING,
            tool_intents=["search_items"],
        ),
        brief=BriefState(event_type="музыкальный вечер", city="Екатеринбург"),
        found_items=[],
    )

    assert "нет строк" in message.lower()
    assert "уточняю бриф" not in message.lower()


@pytest.mark.asyncio
async def test_render_brief_turn_returns_structured_artifact() -> None:
    selected_id = UUID("99999999-9999-9999-9999-999999999991")
    details = FakeCatalogItemDetailsTool(details={selected_id: _detail(selected_id)})
    use_case = ChatTurnUseCase(
        router=HeuristicAssistantRouter(),
        tool_executor=ToolExecutor(
            catalog_search=None,
            item_details=details,
        ),
    )

    response = await use_case.execute(
        AssistantChatRequest(
            session_id=None,
            message="сформируй итоговый бриф",
            brief=BriefState(
                event_type="корпоратив",
                city="Екатеринбург",
                audience_size=120,
                selected_item_ids=[selected_id],
            ),
        ),
    )

    assert response.action_plan is not None
    assert response.action_plan.tool_intents == ["render_event_brief"]
    assert response.action_plan.workflow_stage == EventBriefWorkflowState.BRIEF_RENDERED
    assert response.rendered_brief is not None
    assert response.rendered_brief.evidence["selected_item_ids"] == [str(selected_id)]
    assert details.calls == [selected_id]
    assert "Бриф мероприятия" in response.message
    assert "Основная информация" in response.message
    assert "Тип: корпоратив" in response.message
