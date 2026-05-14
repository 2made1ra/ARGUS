from __future__ import annotations

from uuid import UUID

from app.features.assistant.domain.brief_workflow_policy import BriefWorkflowPolicy
from app.features.assistant.domain.event_brief_interpreter import EventBriefInterpreter
from app.features.assistant.dto import (
    AssistantInterfaceMode,
    BriefState,
    EventBriefWorkflowState,
)


def _plan_for(message: str, brief: BriefState | None = None):
    current_brief = brief if brief is not None else BriefState()
    interpretation = EventBriefInterpreter().interpret(
        message=message,
        brief=current_brief,
    )
    return BriefWorkflowPolicy().plan(
        interpretation=interpretation,
        brief=current_brief,
    )


def test_event_creation_opens_workspace_and_does_not_search_prematurely() -> None:
    plan = _plan_for("Нужно организовать корпоратив на 120 человек в Екатеринбурге")

    assert plan.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert plan.workflow_stage == EventBriefWorkflowState.CLARIFYING
    assert plan.tool_intents == ["update_brief"]
    assert plan.search_requests == []
    assert plan.should_search_now is False
    assert plan.missing_fields[:3] == [
        "date_or_period",
        "venue_status",
        "budget_total",
    ]
    assert 1 <= len(plan.clarification_questions) <= 3


def test_plain_brief_creation_phrase_is_not_final_render_request() -> None:
    current_brief = BriefState()
    interpretation = EventBriefInterpreter().interpret(
        message="сформируй бриф на конференцию",
        brief=current_brief,
    )
    plan = BriefWorkflowPolicy().plan(
        interpretation=interpretation,
        brief=current_brief,
    )

    assert interpretation.intent == "brief_discovery"
    assert interpretation.brief_update.event_type == "конференция"
    assert plan.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert plan.workflow_stage == EventBriefWorkflowState.CLARIFYING
    assert plan.tool_intents == ["update_brief"]
    assert plan.render_requested is False


def test_direct_contractor_search_stays_chat_search() -> None:
    plan = _plan_for("найди подрядчика по свету в Екатеринбурге")

    assert plan.interface_mode == AssistantInterfaceMode.CHAT_SEARCH
    assert plan.workflow_stage == EventBriefWorkflowState.SEARCHING
    assert plan.tool_intents == ["search_items"]
    assert plan.should_search_now is True
    assert plan.search_requests[0].service_category == "свет"
    assert "Екатеринбург" in plan.search_requests[0].query
    assert "date_or_period" not in plan.missing_fields
    assert "venue_status" not in plan.missing_fields


def test_direct_contractor_search_with_active_brief_stays_chat_search() -> None:
    current_brief = BriefState(event_type="корпоратив")
    interpretation = EventBriefInterpreter().interpret(
        message="Найди свет в Екатеринбурге",
        brief=current_brief,
    )
    plan = BriefWorkflowPolicy().plan(
        interpretation=interpretation,
        brief=current_brief,
    )

    assert interpretation.interface_mode == AssistantInterfaceMode.CHAT_SEARCH
    assert interpretation.intent == "supplier_search"
    assert plan.interface_mode == AssistantInterfaceMode.CHAT_SEARCH
    assert plan.workflow_stage == EventBriefWorkflowState.SEARCHING
    assert plan.tool_intents == ["search_items"]
    assert plan.search_requests[0].service_category == "свет"


def test_active_brief_search_with_current_fact_update_uses_workspace() -> None:
    current_brief = BriefState(event_type="корпоратив", audience_size=120)
    interpretation = EventBriefInterpreter().interpret(
        message="Бюджет 2 млн, найди свет в Екатеринбурге",
        brief=current_brief,
    )
    plan = BriefWorkflowPolicy().plan(
        interpretation=interpretation,
        brief=current_brief,
    )

    assert interpretation.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert interpretation.intent == "mixed"
    assert interpretation.brief_update.budget_total == 2_000_000
    assert interpretation.brief_update.city == "Екатеринбург"
    assert interpretation.requested_actions == ["update_brief", "search_items"]
    assert plan.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert plan.workflow_stage == EventBriefWorkflowState.SUPPLIER_SEARCHING
    assert plan.tool_intents == ["update_brief", "search_items"]
    assert plan.search_requests[0].service_category == "свет"


def test_categoryless_contractor_search_asks_for_service_category() -> None:
    plan = _plan_for("найди подрядчика в Екатеринбурге")

    assert plan.interface_mode == AssistantInterfaceMode.CHAT_SEARCH
    assert plan.workflow_stage == EventBriefWorkflowState.SEARCH_CLARIFYING
    assert plan.tool_intents == []
    assert plan.search_requests == []
    assert plan.should_search_now is False
    assert plan.missing_fields == ["service_category"]
    assert plan.clarification_questions == ["Какую услугу или категорию нужно найти?"]


def test_event_domain_term_alone_does_not_force_brief_workspace() -> None:
    plan = _plan_for("найди ведущего на корпоратив в Екатеринбурге")

    assert plan.interface_mode == AssistantInterfaceMode.CHAT_SEARCH
    assert plan.workflow_stage == EventBriefWorkflowState.SEARCHING
    assert plan.tool_intents == ["search_items"]


def test_event_fact_without_creation_intent_does_not_force_brief_workspace() -> None:
    plan = _plan_for("корпоратив в Екатеринбурге")

    assert plan.interface_mode == AssistantInterfaceMode.CHAT_SEARCH
    assert plan.workflow_stage == EventBriefWorkflowState.SEARCH_CLARIFYING
    assert plan.tool_intents == []
    assert plan.search_requests == []
    assert plan.should_search_now is False


def test_preparing_product_presentation_opens_workspace_without_search() -> None:
    plan = _plan_for("Готовим презентацию продукта, нужна площадка и подрядчики")

    assert plan.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert plan.workflow_stage == EventBriefWorkflowState.CLARIFYING
    assert plan.tool_intents == ["update_brief"]
    assert plan.should_search_now is False


def test_active_brief_preserves_workspace_for_contextual_update() -> None:
    plan = _plan_for(
        "тогда добавь площадка без подвеса",
        BriefState(event_type="корпоратив", city="Екатеринбург"),
    )

    assert plan.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE
    assert plan.workflow_stage == EventBriefWorkflowState.CLARIFYING
    assert plan.tool_intents == ["update_brief"]
    assert plan.should_search_now is False


def test_verification_plan_exposes_selected_item_targets() -> None:
    selected_id = UUID("11111111-1111-1111-1111-111111111111")

    plan = _plan_for(
        "проверь найденных подрядчиков",
        BriefState(
            event_type="корпоратив",
            selected_item_ids=[selected_id],
        ),
    )

    assert plan.workflow_stage == EventBriefWorkflowState.SUPPLIER_VERIFICATION
    assert plan.tool_intents == ["verify_supplier_status"]
    assert plan.verification_targets == [selected_id]
