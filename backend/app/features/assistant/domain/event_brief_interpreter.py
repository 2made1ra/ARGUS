from __future__ import annotations

from uuid import UUID

from app.features.assistant.brief import merge_brief
from app.features.assistant.domain.action_detection import (
    detect_action_signals,
    verification_item_ids_for,
)
from app.features.assistant.domain.brief_workflow_policy import (
    missing_event_intake_fields,
)
from app.features.assistant.domain.llm_router import (
    build_llm_router_prompt,
    interpretation_with_reason,
    merge_llm_router_suggestion,
    validate_llm_router_json,
)
from app.features.assistant.domain.slot_extraction import extract_event_brief_slots
from app.features.assistant.dto import (
    AssistantInterfaceMode,
    BriefState,
    ChatTurn,
    Interpretation,
    SearchRequest,
    VisibleCandidate,
)
from app.features.assistant.ports import LLMStructuredRouterPort


class EventBriefInterpreter:
    def __init__(
        self,
        *,
        llm_router: LLMStructuredRouterPort | None = None,
    ) -> None:
        self._llm_router = llm_router

    def interpret(
        self,
        *,
        message: str,
        brief: BriefState,
        visible_candidates: list[VisibleCandidate] | None = None,
        candidate_item_ids: list[UUID] | None = None,
    ) -> Interpretation:
        slots = extract_event_brief_slots(message)
        signals = detect_action_signals(message, brief)
        reason_codes: list[str] = []

        interface_mode = AssistantInterfaceMode.CHAT_SEARCH
        intent = "clarification"
        requested_actions: list[str] = []
        search_requests: list[SearchRequest] = []
        brief_update = BriefState()
        verification_targets: list[UUID] = []

        if signals.verification_requested:
            interface_mode = (
                AssistantInterfaceMode.BRIEF_WORKSPACE
                if _has_active_brief(brief)
                else AssistantInterfaceMode.CHAT_SEARCH
            )
            intent = "verification"
            reason_codes.append("verification_requested")
            verification_targets = _verification_targets_from_context(
                message=message,
                visible_candidates=visible_candidates or [],
                candidate_item_ids=candidate_item_ids or [],
            )
            if verification_targets or brief.selected_item_ids:
                requested_actions.append("verify_supplier_status")
            else:
                reason_codes.append("verification_context_missing")
        elif signals.event_creation or signals.contextual_brief_update:
            interface_mode = AssistantInterfaceMode.BRIEF_WORKSPACE
            intent = "brief_discovery"
            requested_actions.append("update_brief")
            reason_codes.append("event_creation_intent_detected")
            reason_codes.append("brief_update_detected")
            merged_preview = merge_brief(brief, slots)
            brief_update = _with_open_questions(
                slots,
                missing_event_intake_fields(merged_preview),
            )
        elif signals.direct_catalog_search:
            interface_mode = AssistantInterfaceMode.CHAT_SEARCH
            intent = "supplier_search"
            requested_actions.append("search_items")
            reason_codes.append("direct_catalog_search_detected")
            if slots.service_needs:
                reason_codes.append("service_need_detected")
            search_requests = _search_requests(message=message, slots=slots)
        if interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE:
            reason_codes.append("brief_workspace_selected")
        else:
            reason_codes.append("chat_search_selected")

        return Interpretation(
            interface_mode=interface_mode,
            intent=intent,
            confidence=0.88 if reason_codes else 0.4,
            reason_codes=reason_codes,
            brief_update=brief_update,
            service_needs=list(slots.service_needs),
            requested_actions=requested_actions,
            search_requests=search_requests,
            verification_targets=verification_targets,
            missing_fields=(
                ["candidate_context"]
                if signals.verification_requested
                and "verify_supplier_status" not in requested_actions
                else []
            ),
            clarification_questions=(
                [_VERIFICATION_CONTEXT_QUESTION]
                if signals.verification_requested
                and "verify_supplier_status" not in requested_actions
                else []
            ),
        )

    async def interpret_with_llm(
        self,
        *,
        message: str,
        brief: BriefState,
        recent_turns: list[ChatTurn],
        visible_candidates: list[VisibleCandidate],
        candidate_item_ids: list[UUID] | None = None,
    ) -> Interpretation:
        deterministic = self.interpret(
            message=message,
            brief=brief,
            visible_candidates=visible_candidates,
            candidate_item_ids=candidate_item_ids or [],
        )
        if self._llm_router is None:
            return deterministic

        prompt = build_llm_router_prompt(
            message=message,
            brief=brief,
            recent_turns=recent_turns,
            visible_candidates=visible_candidates,
            deterministic=deterministic,
        )
        try:
            raw_response = await self._llm_router.route_structured(prompt=prompt)
        except Exception:
            return interpretation_with_reason(
                deterministic,
                "llm_router_fallback_used",
            )

        suggestion = validate_llm_router_json(raw_response)
        if suggestion is None:
            return interpretation_with_reason(
                deterministic,
                "llm_router_fallback_used",
            )
        return merge_llm_router_suggestion(
            deterministic=deterministic,
            suggestion=suggestion,
        )


_VERIFICATION_CONTEXT_QUESTION = (
    "Каких найденных подрядчиков проверить? Передайте выбранные позиции, "
    "candidate_item_ids, visible_candidates или явные item id."
)


def _verification_targets_from_context(
    *,
    message: str,
    visible_candidates: list[VisibleCandidate],
    candidate_item_ids: list[UUID],
) -> list[UUID]:
    return _dedupe_uuid(
        [
            *candidate_item_ids,
            *[candidate.item_id for candidate in visible_candidates],
            *verification_item_ids_for(message),
        ],
    )


def _dedupe_uuid(item_ids: list[UUID]) -> list[UUID]:
    result: list[UUID] = []
    seen: set[UUID] = set()
    for item_id in item_ids:
        if item_id in seen:
            continue
        result.append(item_id)
        seen.add(item_id)
    return result


def _has_active_brief(brief: BriefState) -> bool:
    return any(
        (
            brief.event_type,
            brief.city,
            brief.date_or_period,
            brief.audience_size,
            brief.venue_status,
            brief.budget_total,
            brief.budget_per_guest,
            brief.required_services,
            brief.service_needs,
            brief.selected_item_ids,
        )
    )


def _with_open_questions(update: BriefState, missing_fields: list[str]) -> BriefState:
    return BriefState(
        event_type=update.event_type,
        event_goal=update.event_goal,
        concept=update.concept,
        format=update.format,
        city=update.city,
        date_or_period=update.date_or_period,
        audience_size=update.audience_size,
        venue=update.venue,
        venue_status=update.venue_status,
        venue_constraints=list(update.venue_constraints),
        duration_or_time_window=update.duration_or_time_window,
        event_level=update.event_level,
        budget=update.budget,
        budget_total=update.budget_total,
        budget_per_guest=update.budget_per_guest,
        budget_notes=update.budget_notes,
        catering_format=update.catering_format,
        technical_requirements=list(update.technical_requirements),
        service_needs=list(update.service_needs),
        required_services=list(update.required_services),
        must_have_services=list(update.must_have_services),
        nice_to_have_services=list(update.nice_to_have_services),
        selected_item_ids=list(update.selected_item_ids),
        constraints=list(update.constraints),
        preferences=list(update.preferences),
        open_questions=list(missing_fields),
    )


def _search_requests(*, message: str, slots: BriefState) -> list[SearchRequest]:
    categories = [
        need.category
        for need in slots.service_needs
        if need.source == "explicit"
    ]
    if not categories:
        categories = list(slots.required_services)
    if not categories:
        return []

    requests: list[SearchRequest] = []
    for index, category in enumerate(categories, start=1):
        query = _search_query(message=message, category=category, slots=slots)
        requests.append(
            SearchRequest(
                query=query,
                service_category=category,
                priority=index,
                limit=8,
            )
        )
    return requests


def _search_query(
    *,
    message: str,
    category: str | None,
    slots: BriefState,
) -> str:
    stripped = _strip_search_prefix(message)
    parts: list[str] = [stripped] if stripped else []
    if category is not None and category not in stripped.lower():
        parts.append(category)
    if slots.event_type is not None:
        parts.append(slots.event_type)
    if slots.audience_size is not None:
        parts.append(f"{slots.audience_size} человек")
    if slots.city is not None:
        parts.append(slots.city)
    if slots.budget_per_guest is not None:
        parts.append(f"до {slots.budget_per_guest} на гостя")
    return " ".join(parts) if parts else stripped


def _strip_search_prefix(message: str) -> str:
    normalized = " ".join(message.strip().split())
    lowered = normalized.lower()
    for prefix in (
        "найди ",
        "подбери ",
        "покажи ",
        "посмотри ",
        "мне нужно ",
        "нужно ",
        "нужен ",
        "нужна ",
        "нужны ",
    ):
        if lowered.startswith(prefix):
            return normalized[len(prefix) :].strip()
    return normalized

__all__ = ["EventBriefInterpreter"]
