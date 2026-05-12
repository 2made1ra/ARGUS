from __future__ import annotations

import re

from app.features.assistant.domain.taxonomy import (
    SERVICE_ALIASES,
    canonical_city_for,
    event_type_for,
    service_bundle_templates_for,
    service_categories_for,
    venue_constraint_templates_for,
)
from app.features.assistant.dto import BriefState, ServiceNeed

_AUDIENCE_RE = re.compile(r"(?P<size>\d{1,5})\s*(?:человек|гостей|гостя|гость)", re.I)
_DATE_RE = re.compile(
    r"\b(?P<date>\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|"
    r"августа|сентября|октября|ноября|декабря))\b",
    re.I,
)
_PER_GUEST_BUDGET_RE = re.compile(
    r"(?:до|около|примерно)?\s*(?P<amount>\d[\d\s]*)\s*(?:руб(?:\.|лей)?\s*)?"
    r"(?:на|за)\s*(?:гостя|человека)",
    re.I,
)
_TOTAL_BUDGET_RE = re.compile(
    r"бюджет\s*(?:около|примерно|до)?\s*(?P<amount>\d+(?:[,.]\d+)?)\s*"
    r"(?P<multiplier>млн|миллиона|тыс|тысяч)?",
    re.I,
)


def extract_event_brief_slots(message: str) -> BriefState:
    normalized = _normalize_spaces(message)
    lower = normalized.lower()
    venue_constraints = _venue_constraints(lower)
    services = _explicit_service_categories(lower, venue_constraints)
    if "музыкаль" in lower and "оборудован" in lower:
        services = [
            "музыкальное оборудование" if service == "оборудование" else service
            for service in services
        ]
    service_needs = _service_needs(lower, services, venue_constraints)
    required_services = _service_projection(
        services,
        lower,
        priority="required",
    )
    must_have_services = _service_projection(
        services,
        lower,
        priority="must_have",
    )
    nice_to_have_services = _nice_to_have_projection(service_needs)

    return BriefState(
        event_type=event_type_for(lower),
        event_goal=_event_goal(normalized),
        concept=_concept(normalized),
        format=_event_format(lower),
        city=canonical_city_for(lower),
        date_or_period=_date_or_period(normalized),
        audience_size=_audience_size(lower),
        venue_status=_venue_status(lower),
        venue_constraints=venue_constraints,
        budget_total=_budget_total(lower),
        budget_per_guest=_budget_per_guest(lower),
        catering_format=_catering_format(lower),
        technical_requirements=_technical_requirements(lower),
        service_needs=service_needs,
        required_services=required_services,
        must_have_services=must_have_services,
        nice_to_have_services=nice_to_have_services,
        preferences=_preferences(lower),
    )


def _normalize_spaces(value: str) -> str:
    return " ".join(value.strip().split())


def _audience_size(lower: str) -> int | None:
    match = _AUDIENCE_RE.search(lower)
    if match is None:
        return None
    return int(match.group("size"))


def _date_or_period(normalized: str) -> str | None:
    match = _DATE_RE.search(normalized)
    if match is None:
        return None
    return match.group("date")


def _venue_status(lower: str) -> str | None:
    if "площадка уже есть" in lower or "площадка есть" in lower:
        return "площадка есть"
    if "есть площадка" in lower:
        return "площадка есть"
    if "площадки нет" in lower:
        return "площадки нет"
    if "нужна площадка" in lower or "подобрать площадку" in lower:
        return "площадку нужно подобрать"
    return None


def _venue_constraints(lower: str) -> list[str]:
    constraints: list[str] = []
    if "без подвеса" in lower:
        constraints.append("площадка без подвеса")
    if "низк" in lower and "потол" in lower:
        constraints.append("низкие потолки")
    return constraints


def _explicit_service_categories(
    lower: str,
    venue_constraints: list[str],
) -> list[str]:
    categories = service_categories_for(lower)
    if "площадка без подвеса" not in venue_constraints:
        return categories
    if _requests_venue_search(lower):
        return categories
    return [category for category in categories if category != "площадка"]


def _requests_venue_search(lower: str) -> bool:
    return any(
        phrase in lower
        for phrase in (
            "нужна площадка",
            "подобрать площадку",
            "найди площадку",
            "покажи площадку",
            "посмотри площадку",
        )
    )


def _service_needs(
    lower: str,
    services: list[str],
    venue_constraints: list[str],
) -> list[ServiceNeed]:
    needs: list[ServiceNeed] = []
    for category in services:
        priority = _priority_for_category(lower, category)
        needs.append(
            ServiceNeed(
                category=category,
                priority=priority,
                source="explicit",
            )
        )
        needs.extend(
            ServiceNeed(
                category=template.category,
                priority=template.priority,
                source=template.source,
                reason=template.reason,
                notes=template.notes,
            )
            for template in service_bundle_templates_for(category)
        )

    needs.extend(
        ServiceNeed(
            category=template.category,
            priority=template.priority,
            source=template.source,
            reason=template.reason,
            notes=template.notes,
        )
        for template in venue_constraint_templates_for(venue_constraints)
    )
    return _unique_service_needs(needs)


def _priority_for_category(lower: str, category: str) -> str:
    category_position = lower.find(category)
    if category_position < 0:
        for alias_category in service_categories_for(lower):
            if alias_category == category:
                category_position = _first_alias_position(lower, category)
                break
    context = _priority_context(lower, category_position)
    if any(marker in context for marker in ("обязательно", "критично", "must have")):
        return "must_have"
    if any(
        marker in context
        for marker in ("хорошо бы", "желательно", "можно добавить", "опционально")
    ):
        return "nice_to_have"
    return "required"


def _first_alias_position(lower: str, category: str) -> int:
    positions: list[int] = []
    for service_alias in SERVICE_ALIASES:
        if service_alias.category != category:
            continue
        for alias in service_alias.aliases:
            position = lower.find(alias)
            if position >= 0:
                positions.append(position)
    if positions:
        return min(positions)
    return -1


def _priority_context(lower: str, position: int) -> str:
    if position < 0:
        return lower
    starts = [lower.rfind(separator, 0, position) for separator in (",", ";", ".")]
    start = max(starts)
    ends = [
        next_position
        for separator in (",", ";", ".")
        if (next_position := lower.find(separator, position)) >= 0
    ]
    end = min(ends) if ends else len(lower)
    return lower[start + 1 : end]


def _service_projection(
    services: list[str],
    lower: str,
    *,
    priority: str,
) -> list[str]:
    return [
        service
        for service in services
        if _priority_for_category(lower, service) == priority
    ]


def _nice_to_have_projection(service_needs: list[ServiceNeed]) -> list[str]:
    return _unique(
        [
            need.category
            for need in service_needs
            if need.priority == "nice_to_have"
        ]
    )


def _preferences(lower: str) -> list[str]:
    preferences: list[str] = []
    if "без премиума" in lower:
        preferences.append("без премиума")
    if "быстро" in lower:
        preferences.append("быстро")
    return preferences


def _technical_requirements(lower: str) -> list[str]:
    requirements: list[str] = []
    if "монтаж только ночью" in lower or "только ночью" in lower:
        requirements.append("монтаж только ночью")
    if "ночной монтаж" in lower:
        requirements.append("ночной монтаж")
    return _unique(requirements)


def _budget_per_guest(lower: str) -> int | None:
    match = _PER_GUEST_BUDGET_RE.search(lower)
    if match is None:
        return None
    return _parse_integer(match.group("amount"))


def _budget_total(lower: str) -> int | None:
    if _PER_GUEST_BUDGET_RE.search(lower) is not None:
        return None
    match = _TOTAL_BUDGET_RE.search(lower)
    if match is None:
        return None
    amount = float(match.group("amount").replace(",", "."))
    multiplier = match.group("multiplier")
    if multiplier in {"млн", "миллиона"}:
        amount *= 1_000_000
    elif multiplier in {"тыс", "тысяч"}:
        amount *= 1_000
    return int(amount)


def _parse_integer(value: str) -> int:
    return int(value.replace(" ", ""))


def _catering_format(lower: str) -> str | None:
    for value in ("фуршет", "банкет", "кофе-брейк"):
        if value in lower:
            return value
    return None


def _event_format(lower: str) -> str | None:
    for value in ("гибрид", "онлайн", "офлайн"):
        if value in lower:
            return value
    return None


def _event_goal(normalized: str) -> str | None:
    match = re.search(
        r"(?:цель|задача)\s*[—\-:]?\s*(?P<goal>[^,.;]+)",
        normalized,
        re.I,
    )
    if match is None:
        return None
    return match.group("goal").strip().lower()


def _concept(normalized: str) -> str | None:
    match = re.search(
        r"(?:концепция|концепт|в стиле)\s*[—\-:]?\s*(?P<concept>[^,.;]+)",
        normalized,
        re.I,
    )
    if match is None:
        return None
    return match.group("concept").strip().lower()


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


def _unique_service_needs(needs: list[ServiceNeed]) -> list[ServiceNeed]:
    result: list[ServiceNeed] = []
    seen: set[tuple[str, str, str, str | None, str | None]] = set()
    for need in needs:
        key = (
            need.category,
            need.priority,
            need.source,
            need.reason,
            need.notes,
        )
        if key in seen:
            continue
        result.append(need)
        seen.add(key)
    return result


__all__ = ["extract_event_brief_slots"]
