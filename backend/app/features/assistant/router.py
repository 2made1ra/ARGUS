from __future__ import annotations

from typing import Any
from uuid import UUID

from app.features.assistant.domain.brief_workflow_policy import BriefWorkflowPolicy
from app.features.assistant.domain.event_brief_interpreter import EventBriefInterpreter
from app.features.assistant.domain.slot_extraction import extract_event_brief_slots
from app.features.assistant.dto import (
    ActionPlan,
    BriefState,
    ChatTurn,
    Interpretation,
    RouterDecision,
    VisibleCandidate,
)
from app.features.assistant.ports import LLMStructuredRouterPort


class HeuristicAssistantRouter:
    def __init__(
        self,
        *,
        llm_router: LLMStructuredRouterPort | None = None,
    ) -> None:
        self._llm_router = llm_router

    async def route(
        self,
        *,
        message: str,
        brief: BriefState,
        recent_turns: list[ChatTurn] | None = None,
        visible_candidates: list[VisibleCandidate] | None = None,
        candidate_item_ids: list[UUID] | None = None,
    ) -> RouterDecision:
        normalized = _normalize_spaces(message)
        lower = normalized.lower()
        if not normalized or _is_too_ambiguous(lower):
            return _clarification_decision(brief)

        interpretation = await EventBriefInterpreter(
            llm_router=self._llm_router,
        ).interpret_with_llm(
            message=normalized,
            brief=brief,
            recent_turns=recent_turns if recent_turns is not None else [],
            visible_candidates=(
                visible_candidates if visible_candidates is not None else []
            ),
            candidate_item_ids=(
                candidate_item_ids if candidate_item_ids is not None else []
            ),
        )
        action_plan = BriefWorkflowPolicy().plan(
            interpretation=interpretation,
            brief=brief,
        )
        return _decision_from_interpretation(
            interpretation=interpretation,
            action_plan=action_plan,
            lower=lower,
        )


def _normalize_spaces(value: str) -> str:
    return " ".join(value.strip().split())


def _is_too_ambiguous(lower: str) -> bool:
    return len(lower) < 12 or lower in {"подскажи", "помоги", "нужно", "хочу"}


def _supplier_update(update: BriefState, lower: str) -> BriefState:
    services = update.required_services
    if not services and "оборудован" in lower:
        services = ["оборудование"]
    return BriefState(
        event_type=update.event_type,
        audience_size=update.audience_size,
        required_services=services,
    )


def _missing_fields(brief: BriefState) -> list[str]:
    required = ["city", "audience_size", "venue_status"]
    return [field_name for field_name in required if getattr(brief, field_name) is None]


def _known_facts(brief: BriefState) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    for field_name in (
        "event_type",
        "event_goal",
        "concept",
        "format",
        "city",
        "date_or_period",
        "audience_size",
        "venue",
        "venue_status",
        "budget_total",
        "budget_per_guest",
        "budget_notes",
        "duration_or_time_window",
        "budget",
        "event_level",
    ):
        value = getattr(brief, field_name)
        if value is not None:
            facts[field_name] = value
    for field_name in (
        "venue_constraints",
        "technical_requirements",
        "required_services",
        "constraints",
        "preferences",
    ):
        value = getattr(brief, field_name)
        if value:
            facts[field_name] = value
    return facts


def _decision_from_interpretation(
    *,
    interpretation: Interpretation,
    action_plan: ActionPlan,
    lower: str,
) -> RouterDecision:
    brief_update = interpretation.brief_update
    if interpretation.intent == "supplier_search":
        slots = extract_event_brief_slots(lower)
        brief_update = _supplier_update(slots, lower)
    search_query = (
        action_plan.search_requests[0].query if action_plan.search_requests else None
    )
    return RouterDecision(
        intent=interpretation.intent,
        confidence=interpretation.confidence,
        known_facts=_known_facts(brief_update),
        missing_fields=list(action_plan.missing_fields),
        should_search_now=action_plan.should_search_now,
        search_query=search_query,
        brief_update=brief_update,
        interface_mode=action_plan.interface_mode,
        workflow_stage=action_plan.workflow_stage,
        reason_codes=list(interpretation.reason_codes),
        search_requests=list(action_plan.search_requests),
        tool_intents=list(action_plan.tool_intents),
        clarification_questions=list(action_plan.clarification_questions),
        user_visible_summary=interpretation.user_visible_summary,
        action_plan=action_plan,
    )


def _clarification_decision(brief: BriefState) -> RouterDecision:
    return RouterDecision(
        intent="clarification",
        confidence=0.4,
        known_facts=_known_facts(brief),
        missing_fields=_missing_fields(brief),
        should_search_now=False,
        search_query=None,
        brief_update=BriefState(),
    )


__all__ = ["HeuristicAssistantRouter"]
