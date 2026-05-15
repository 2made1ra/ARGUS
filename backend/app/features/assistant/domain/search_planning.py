from __future__ import annotations

import re
from dataclasses import fields

from app.features.assistant.domain.slot_extraction import extract_event_brief_slots
from app.features.assistant.domain.taxonomy import canonical_city_for
from app.features.assistant.dto import (
    BriefState,
    CatalogSearchFilters,
    EventBriefWorkflowState,
    RouterDecision,
    SearchRequest,
)

_DEFAULT_LIMIT = 8
_MAX_PLANNED_SEARCHES = 3
_AUDIENCE_RE = re.compile(r"(?P<size>\d{1,5})\s*(?:человек|гостей|гостя|гость)", re.I)
_PER_GUEST_BUDGET_RE = re.compile(
    r"(?:до|около|примерно)?\s*\d[\d\s]*\s*(?:руб(?:\.|лей)?\s*)?"
    r"(?:на|за)\s*(?:гостя|человека)",
    re.I,
)
_TOTAL_BUDGET_RE = re.compile(
    r"бюджет\w*\s*(?:около|примерно|до)?\s*"
    r"\d+(?:[\s\u00a0]\d{3})*(?:[,.]\d+)?\s*"
    r"(?:млн\.?|миллион(?:а|ов)?|тыс\.?|тысяч[аи]?)?",
    re.I,
)
_CITY_PHRASE_RE = re.compile(
    r"\b(?:в|во|город|г\.?)\s+"
    r"(?:екатеринбург(?:е)?|екате|екб|москв(?:а|е)|санкт-петербург(?:е)?|"
    r"петербург(?:е)?|спб)\b",
    re.I,
)
_EVENT_TYPE_WORD_RE = re.compile(
    r"\b(?:корпоратив\w*|конференц\w*|презентац\w*|выпускн\w*|мероприят\w*)\b",
    re.I,
)
_SEARCH_REFINEMENT_RE = re.compile(
    r"\b(?:кто сможет|быстро|срочно|еще|ещё|другие|варианты|под это)\b",
    re.I,
)


class SearchPlanner:
    def __init__(self, *, max_searches_per_turn: int = _MAX_PLANNED_SEARCHES) -> None:
        self._max_searches_per_turn = max(0, max_searches_per_turn)

    def plan(
        self,
        *,
        decision: RouterDecision,
        brief_before: BriefState,
        brief_after: BriefState,
        workflow_stage: EventBriefWorkflowState,
    ) -> list[SearchRequest]:
        del workflow_stage
        requests = _requests_from_decision(decision, brief_after)
        if not requests:
            return []

        all_request_categories = [
            request.service_category
            for request in requests
            if request.service_category is not None
        ]
        ordered = sorted(
            enumerate(requests),
            key=lambda item: _request_sort_key(
                index=item[0],
                request=item[1],
                all_categories=all_request_categories,
            ),
        )
        limited = [
            request
            for _index, request in ordered[: self._max_searches_per_turn]
        ]
        all_categories = [
            request.service_category
            for request in limited
            if request.service_category is not None
        ]
        fallback_slots = extract_event_brief_slots(
            " ".join(request.query for request in limited),
        )

        planned: list[SearchRequest] = []
        for index, request in enumerate(limited, start=1):
            filters = _planned_filters(
                request=request,
                brief_before=brief_before,
                brief_after=brief_after,
                fallback_slots=fallback_slots,
            )
            planned.append(
                SearchRequest(
                    query=_planned_query(
                        request=request,
                        brief_before=brief_before,
                        brief_after=brief_after,
                        fallback_slots=fallback_slots,
                        all_categories=all_categories,
                    ),
                    service_category=request.service_category,
                    filters=filters,
                    priority=index,
                    limit=request.limit,
                ),
            )
        return planned


def _requests_from_decision(
    decision: RouterDecision,
    brief_after: BriefState,
) -> list[SearchRequest]:
    if decision.action_plan is not None and decision.action_plan.search_requests:
        return _expand_uncategorized_requests(
            list(decision.action_plan.search_requests),
            brief_after,
        )
    if decision.search_requests:
        return _expand_uncategorized_requests(
            list(decision.search_requests),
            brief_after,
        )
    if decision.search_query is not None:
        categories = _service_categories_from_brief(brief_after)
        if not categories:
            return [SearchRequest(query=decision.search_query, limit=_DEFAULT_LIMIT)]
        return [
            SearchRequest(
                query=decision.search_query,
                service_category=category,
                priority=index,
                limit=_DEFAULT_LIMIT,
            )
            for index, category in enumerate(categories, start=1)
        ]
    return []


def _expand_uncategorized_requests(
    requests: list[SearchRequest],
    brief_after: BriefState,
) -> list[SearchRequest]:
    categories = _service_categories_from_brief(brief_after)
    if not categories:
        return requests

    expanded: list[SearchRequest] = []
    for request in requests:
        if request.service_category is not None:
            expanded.append(request)
            continue
        expanded.extend(
            SearchRequest(
                query=request.query,
                service_category=category,
                filters=request.filters,
                priority=request.priority + index,
                limit=request.limit,
            )
            for index, category in enumerate(categories)
        )
    return expanded


def _service_categories_from_brief(brief: BriefState) -> list[str]:
    categories = [
        *[need.category for need in brief.service_needs if need.source == "explicit"],
        *brief.required_services,
        *brief.must_have_services,
    ]
    return _dedupe(categories)


def _planned_filters(
    *,
    request: SearchRequest,
    brief_before: BriefState,
    brief_after: BriefState,
    fallback_slots: BriefState,
) -> CatalogSearchFilters:
    existing = request.filters
    city = (
        existing.supplier_city_normalized
        or _normalized_city(brief_after.city)
        or _normalized_city(brief_before.city)
        or _normalized_city(fallback_slots.city)
        or _normalized_city(canonical_city_for(request.query.lower()) or None)
    )
    unit_price_max = existing.unit_price_max
    if unit_price_max is None and request.service_category == "кейтеринг":
        unit_price_max = (
            brief_after.budget_per_guest
            or brief_before.budget_per_guest
            or fallback_slots.budget_per_guest
        )

    values = {field.name: getattr(existing, field.name) for field in fields(existing)}
    values["supplier_city_normalized"] = city
    values["unit_price_max"] = unit_price_max
    return CatalogSearchFilters(**values)


def _planned_query(
    *,
    request: SearchRequest,
    brief_before: BriefState,
    brief_after: BriefState,
    fallback_slots: BriefState,
    all_categories: list[str],
) -> str:
    base_query = _base_query_for_request(request, all_categories)
    parts: list[str] = []
    _append_unique(parts, request.service_category)
    _append_unique(
        parts,
        _semantic_query_tail(
            base_query,
            service_category=request.service_category,
            brief_before=brief_before,
            brief_after=brief_after,
            fallback_slots=fallback_slots,
        ),
    )
    return " ".join(parts)


def _semantic_query_tail(
    value: str | None,
    *,
    service_category: str | None,
    brief_before: BriefState,
    brief_after: BriefState,
    fallback_slots: BriefState,
) -> str | None:
    if value is None:
        return None
    cleaned = value
    cleaned = _AUDIENCE_RE.sub(" ", cleaned)
    cleaned = _PER_GUEST_BUDGET_RE.sub(" ", cleaned)
    cleaned = _TOTAL_BUDGET_RE.sub(" ", cleaned)
    cleaned = _CITY_PHRASE_RE.sub(" ", cleaned)
    cleaned = _EVENT_TYPE_WORD_RE.sub(" ", cleaned)
    cleaned = _SEARCH_REFINEMENT_RE.sub(" ", cleaned)
    if service_category is not None:
        cleaned = _remove_phrase(cleaned, service_category)
    for structural_value in _structural_values(
        brief_before=brief_before,
        brief_after=brief_after,
        fallback_slots=fallback_slots,
    ):
        cleaned = _remove_phrase(cleaned, structural_value)
    cleaned = re.sub(r"\b(?:для|на|в|во|по|под|до|за)\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-?!")
    return cleaned or None


def _structural_values(
    *,
    brief_before: BriefState,
    brief_after: BriefState,
    fallback_slots: BriefState,
) -> list[str]:
    values: list[str] = []
    for brief in (brief_after, brief_before, fallback_slots):
        values.extend(
            value
            for value in (
                brief.event_type,
                brief.city,
                brief.concept,
                brief.event_level,
                brief.date_or_period,
            )
            if value is not None
        )
        values.extend(brief.venue_constraints)
        values.extend(brief.constraints)
        values.extend(brief.preferences)
    return _dedupe(values)


def _remove_phrase(value: str, phrase: str) -> str:
    escaped = re.escape(phrase)
    return re.sub(
        rf"(?<![0-9a-zа-я]){escaped}(?![0-9a-zа-я])",
        " ",
        value,
        flags=re.I,
    )


def _base_query_for_request(
    request: SearchRequest,
    all_categories: list[str],
) -> str | None:
    base_query = _strip_search_prefix(request.query)
    lowered = base_query.lower()
    matched_categories = [
        category
        for category in all_categories
        if category is not None and category.lower() in lowered
    ]
    if len(matched_categories) > 1:
        return None
    if request.service_category is not None:
        category = request.service_category.lower()
        if lowered == category:
            return None
        if lowered.startswith(category):
            remainder = base_query[len(request.service_category) :].strip(" ,.;:-")
            return remainder or None
    return base_query or None


def _request_sort_key(
    *,
    index: int,
    request: SearchRequest,
    all_categories: list[str],
) -> tuple[int, int, int]:
    if _query_mentions_multiple_categories(request.query, all_categories):
        position = _category_position(request.query, request.service_category)
        if position >= 0:
            return (0, position, index)
    return (1, request.priority, index)


def _query_mentions_multiple_categories(query: str, all_categories: list[str]) -> bool:
    lowered = query.lower()
    return sum(1 for category in all_categories if category.lower() in lowered) > 1


def _category_position(query: str, category: str | None) -> int:
    if category is None:
        return -1
    return query.lower().find(category.lower())


def _strip_search_prefix(message: str) -> str:
    normalized = " ".join(message.strip().split())
    lowered = normalized.lower()
    for prefix in (
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


def _audience_size(value: str) -> int | None:
    match = _AUDIENCE_RE.search(value)
    if match is None:
        return None
    return int(match.group("size"))


def _normalized_city(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.lower().replace("ё", "е").split())
    normalized = re.sub(r"^(г\.?|город)\s+", "", normalized)
    return normalized or None


def _append_unique(parts: list[str], value: str | None) -> None:
    if value is None:
        return
    normalized = " ".join(value.split())
    if not normalized:
        return
    lowered = normalized.lower()
    existing = " ".join(parts).lower()
    if lowered in existing:
        return
    parts.append(normalized)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


__all__ = ["SearchPlanner"]
