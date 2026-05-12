from __future__ import annotations

from app.features.assistant.brief import merge_brief
from app.features.assistant.domain.brief_workflow_policy import BriefWorkflowPolicy
from app.features.assistant.domain.event_brief_interpreter import EventBriefInterpreter
from app.features.assistant.domain.response_composer import ResponseComposer
from app.features.assistant.dto import (
    AssistantInterfaceMode,
    BriefState,
    FoundCatalogItem,
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
