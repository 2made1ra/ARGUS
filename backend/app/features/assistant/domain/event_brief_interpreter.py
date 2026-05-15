from __future__ import annotations

import re
from uuid import UUID

from app.features.assistant.brief import merge_brief
from app.features.assistant.domain.action_detection import (
    ActionSignals,
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
from app.features.assistant.domain.taxonomy import (
    canonical_city_for,
    service_categories_for,
)
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
        recent_turns: list[ChatTurn] | None = None,
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
        comparison_targets: list[UUID] = []

        if signals.render_requested and (
            _has_active_brief(brief) or not signals.event_creation
        ):
            interface_mode = AssistantInterfaceMode.BRIEF_WORKSPACE
            intent = "render_brief"
            reason_codes.append("render_brief_requested")
            if _has_active_brief(brief):
                requested_actions.append("render_event_brief")
            else:
                reason_codes.append("brief_context_missing")
        elif signals.selection_requested:
            interface_mode = (
                AssistantInterfaceMode.BRIEF_WORKSPACE
                if _has_active_brief(brief)
                else AssistantInterfaceMode.CHAT_SEARCH
            )
            intent = "selection"
            reason_codes.append("selection_requested")
            selection_targets = _selection_targets_from_context(
                message=message,
                visible_candidates=visible_candidates or [],
            )
            if selection_targets:
                requested_actions.append("select_item")
                brief_update = BriefState(selected_item_ids=selection_targets)
                reason_codes.append("contextual_reference_resolved")
            else:
                reason_codes.append("context_missing_for_reference")
        elif signals.comparison_requested:
            interface_mode = (
                AssistantInterfaceMode.BRIEF_WORKSPACE
                if _has_active_brief(brief)
                else AssistantInterfaceMode.CHAT_SEARCH
            )
            intent = "comparison"
            reason_codes.append("comparison_requested")
            comparison_targets = _comparison_targets_from_context(
                message=message,
                visible_candidates=visible_candidates or [],
                candidate_item_ids=candidate_item_ids or [],
            )
            if len(comparison_targets) >= 2:
                requested_actions.append("compare_items")
                reason_codes.append("contextual_reference_resolved")
            else:
                reason_codes.append("comparison_context_missing")
        elif signals.verification_requested:
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
        elif _is_contextual_search_refinement(message=message, slots=slots) and (
            recent_categories := _recent_search_categories(recent_turns or [])
        ):
            interface_mode = AssistantInterfaceMode.CHAT_SEARCH
            intent = "supplier_search"
            requested_actions.append("search_items")
            reason_codes.append("direct_catalog_search_detected")
            reason_codes.append("recent_turn_service_context_used")
            search_requests = _search_requests_for_categories(
                message=message,
                slots=slots,
                categories=recent_categories,
            )
        elif (
            _has_active_brief(brief)
            and not signals.direct_catalog_search
            and _has_follow_up_brief_update(slots)
        ):
            interface_mode = AssistantInterfaceMode.BRIEF_WORKSPACE
            intent = "brief_discovery"
            requested_actions.append("update_brief")
            reason_codes.append("brief_update_detected")
            merged_preview = merge_brief(brief, slots)
            brief_update = _with_open_questions(
                slots,
                missing_event_intake_fields(merged_preview),
            )
        elif _has_active_brief(brief) and _is_brief_clarification_request(message):
            interface_mode = AssistantInterfaceMode.BRIEF_WORKSPACE
            intent = "clarification"
            reason_codes.append("brief_clarification_requested")
        elif (
            signals.direct_catalog_search
            and not signals.event_creation
            and _has_active_brief(brief)
            and not _has_service_category(slots)
            and (
                brief_context_requests := _search_requests_from_brief_context(
                    message=message,
                    brief=brief,
                    slots=slots,
                )
            )
        ):
            interface_mode = AssistantInterfaceMode.BRIEF_WORKSPACE
            intent = "supplier_search"
            requested_actions.append("search_items")
            reason_codes.append("brief_context_search_requested")
            reason_codes.append("service_need_inferred_from_brief")
            search_requests = brief_context_requests
        elif (
            signals.direct_catalog_search
            and not signals.event_creation
            and _has_active_brief(brief)
            and (
                signals.contextual_brief_update
                or _has_brief_update_for_search(slots)
            )
        ):
            interface_mode = AssistantInterfaceMode.BRIEF_WORKSPACE
            intent = "mixed"
            requested_actions.extend(["update_brief", "search_items"])
            reason_codes.append("brief_update_detected")
            reason_codes.append("search_action_detected")
            if slots.service_needs:
                reason_codes.append("service_need_detected")
            merged_preview = merge_brief(brief, slots)
            brief_update = _with_open_questions(
                slots,
                missing_event_intake_fields(merged_preview),
            )
            search_requests = _search_requests(message=message, slots=slots)
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
            comparison_targets=comparison_targets,
            missing_fields=(
                ["candidate_context"]
                if (
                    signals.verification_requested
                    and "verify_supplier_status" not in requested_actions
                )
                or (
                    signals.selection_requested
                    and "select_item" not in requested_actions
                )
                or (
                    signals.comparison_requested
                    and "compare_items" not in requested_actions
                )
                else []
            ),
            clarification_questions=(
                [_context_question_for(signals)]
                if (
                    signals.verification_requested
                    and "verify_supplier_status" not in requested_actions
                )
                or (
                    signals.selection_requested
                    and "select_item" not in requested_actions
                )
                or (
                    signals.comparison_requested
                    and "compare_items" not in requested_actions
                )
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
            recent_turns=recent_turns,
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
_SELECTION_CONTEXT_QUESTION = (
    "Какой вариант добавить? Передайте visible_candidates с ordinal и item_id "
    "или выберите позицию в карточках."
)
_COMPARISON_CONTEXT_QUESTION = (
    "Какие две позиции сравнить? Передайте visible_candidates с ordinal и "
    "item_id или candidate_item_ids для видимых карточек."
)


def _context_question_for(signals: ActionSignals) -> str:
    if signals.selection_requested:
        return _SELECTION_CONTEXT_QUESTION
    if signals.comparison_requested:
        return _COMPARISON_CONTEXT_QUESTION
    return _VERIFICATION_CONTEXT_QUESTION


def _selection_targets_from_context(
    *,
    message: str,
    visible_candidates: list[VisibleCandidate],
) -> list[UUID]:
    if not visible_candidates:
        return []
    ordinals = _selection_ordinals_for(message)
    if not ordinals:
        return []
    candidates_by_ordinal = {
        candidate.ordinal: candidate.item_id for candidate in visible_candidates
    }
    return _dedupe_uuid(
        [
            candidates_by_ordinal[ordinal]
            for ordinal in ordinals
            if ordinal in candidates_by_ordinal
        ],
    )


def _selection_ordinals_for(message: str) -> list[int]:
    lower = message.lower()
    ordinals: list[int] = []
    target_noun = r"(?:вариант\w*|позици\w*|карточк\w*)"
    if re.search(rf"\bпервые\s+(?:два|2)\s+{target_noun}\b", lower):
        ordinals.extend([1, 2])
    ordinal_markers = {
        1: r"(?:перв(?:ый|ого|ую)|1-й|1)",
        2: r"(?:втор(?:ой|ого|ую)|2-й|2)",
        3: r"(?:трет(?:ий|ьего|ью)|3-й|3)",
    }
    for ordinal, marker_pattern in ordinal_markers.items():
        if re.search(rf"\b{marker_pattern}\s+{target_noun}\b", lower) or re.search(
            rf"\b{target_noun}\s+{marker_pattern}\b",
            lower,
        ):
            ordinals.append(ordinal)
    return _dedupe_int(ordinals)


def _comparison_targets_from_context(
    *,
    message: str,
    visible_candidates: list[VisibleCandidate],
    candidate_item_ids: list[UUID],
) -> list[UUID]:
    ordinals = _comparison_ordinals_for(message)
    visible_targets = _targets_for_ordinals(
        ordinals=ordinals,
        visible_candidates=visible_candidates,
    )
    if ordinals:
        if len(visible_targets) >= 2:
            return visible_targets[:2]
        if not visible_candidates and len(candidate_item_ids) >= 2:
            return _dedupe_uuid(candidate_item_ids)[:2]
        return visible_targets[:2]
    if len(visible_candidates) >= 2:
        return _dedupe_uuid(
            [
                candidate.item_id
                for candidate in sorted(
                    visible_candidates,
                    key=lambda candidate: candidate.ordinal,
                )
            ],
        )[:2]
    if len(candidate_item_ids) >= 2:
        return _dedupe_uuid(candidate_item_ids)[:2]
    return []


def _comparison_ordinals_for(message: str) -> list[int]:
    lower = message.lower()
    if re.search(r"\bперв(?:ые|ых)\s+(?:два|2)\b", lower):
        return [1, 2]
    if re.search(r"\bперв(?:ый|ого|ую)\s+и\s+втор(?:ой|ого|ую)\b", lower):
        return [1, 2]
    if re.search(r"\bвтор(?:ой|ого|ую)\s+и\s+трет(?:ий|ьего|ью)\b", lower):
        return [2, 3]
    return _selection_ordinals_for(message)


def _targets_for_ordinals(
    *,
    ordinals: list[int],
    visible_candidates: list[VisibleCandidate],
) -> list[UUID]:
    if not visible_candidates or not ordinals:
        return []
    candidates_by_ordinal = {
        candidate.ordinal: candidate.item_id for candidate in visible_candidates
    }
    return _dedupe_uuid(
        [
            candidates_by_ordinal[ordinal]
            for ordinal in ordinals
            if ordinal in candidates_by_ordinal
        ],
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


def _dedupe_int(values: list[int]) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
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
        exact_query = _categoryless_exact_search_query(message)
        if exact_query is None:
            return []
        return [SearchRequest(query=exact_query, service_category=None, limit=8)]

    return _search_requests_for_categories(
        message=message,
        slots=slots,
        categories=categories,
    )


def _search_requests_from_brief_context(
    *,
    message: str,
    brief: BriefState,
    slots: BriefState,
) -> list[SearchRequest]:
    categories = _brief_context_categories(brief)
    if not categories:
        return []
    return _search_requests_for_categories(
        message=message,
        slots=merge_brief(brief, slots),
        categories=categories,
    )


def _brief_context_categories(brief: BriefState) -> list[str]:
    categories: list[str] = []
    categories.extend(
        need.category for need in brief.service_needs if need.source == "explicit"
    )
    categories.extend(brief.required_services)
    categories.extend(brief.must_have_services)

    venue_needs_search = brief.venue_status in {
        "площадки нет",
        "площадку нужно подобрать",
    }
    if venue_needs_search:
        categories.append("площадка")
    if brief.event_type == "музыкальный вечер":
        categories.extend(["звук", "свет"])
    return _dedupe_str(categories)


def _search_requests_for_categories(
    *,
    message: str,
    slots: BriefState,
    categories: list[str],
) -> list[SearchRequest]:
    requests: list[SearchRequest] = []
    for index, category in enumerate(_dedupe_str(categories), start=1):
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


def _is_contextual_search_refinement(
    *,
    message: str,
    slots: BriefState,
) -> bool:
    if _has_service_category(slots):
        return False
    lower = message.lower()
    return (
        canonical_city_for(lower) is not None
        or bool(slots.preferences)
        or any(
            marker in lower
            for marker in (
                "кто сможет",
                "быстро",
                "срочно",
                "еще",
                "ещё",
                "другие",
                "варианты",
                "под это",
            )
        )
    )


def _has_service_category(slots: BriefState) -> bool:
    return bool(slots.service_needs or slots.required_services)


def _has_follow_up_brief_update(slots: BriefState) -> bool:
    return any(
        (
            slots.event_type,
            slots.event_goal,
            slots.concept,
            slots.format,
            slots.city,
            slots.date_or_period,
            slots.audience_size,
            slots.venue_status,
            slots.venue_constraints,
            slots.duration_or_time_window,
            slots.event_level,
            slots.budget_total,
            slots.budget_per_guest,
            slots.budget_notes,
            slots.catering_format,
            slots.technical_requirements,
            slots.service_needs,
            slots.required_services,
            slots.must_have_services,
            slots.nice_to_have_services,
            slots.constraints,
            slots.preferences,
        )
    )


def _is_brief_clarification_request(message: str) -> bool:
    lower = message.lower()
    return "что еще нужно уточнить" in lower or "что ещё нужно уточнить" in lower


def _has_brief_update_for_search(slots: BriefState) -> bool:
    return any(
        (
            slots.venue_status,
            slots.venue_constraints,
            slots.budget_total,
            slots.budget_notes,
            slots.catering_format,
            slots.technical_requirements,
            slots.constraints,
        )
    )


def _recent_search_categories(recent_turns: list[ChatTurn]) -> list[str]:
    categories: list[str] = []
    for turn in reversed(recent_turns[-6:]):
        if turn.role != "user":
            continue
        categories.extend(service_categories_for(turn.content))
        if categories:
            break
    return _dedupe_str(categories)


def _dedupe_str(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


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
        "найди мне ",
        "подбери мне ",
        "покажи мне ",
        "найди ",
        "подбери ",
        "покажи ",
        "посмотри ",
        "мне нужен ",
        "мне нужна ",
        "мне нужно ",
        "мне нужны ",
        "нужно ",
        "нужен ",
        "нужна ",
        "нужны ",
    ):
        if lowered.startswith(prefix):
            return normalized[len(prefix) :].strip()
    return normalized


def _categoryless_exact_search_query(message: str) -> str | None:
    stripped = _strip_search_prefix(message)
    cleaned = re.sub(
        r"^(?:поставщик|поставщика|подрядчик|подрядчика)\s+",
        "",
        stripped,
        flags=re.IGNORECASE,
    ).strip()
    inn_match = re.search(r"\bинн\s+(\d{10}|\d{12})\b", cleaned, flags=re.IGNORECASE)
    if inn_match is not None:
        return inn_match.group(1)
    if re.fullmatch(r"\d{10}|\d{12}", cleaned):
        return cleaned
    if re.search(r"\b(?:ооо|ао|ано|ип|зао|пао)\b", cleaned, flags=re.IGNORECASE):
        return cleaned
    return None

__all__ = ["EventBriefInterpreter"]
