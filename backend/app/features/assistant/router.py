from __future__ import annotations

import re
from typing import Any

from app.features.assistant.brief import merge_brief
from app.features.assistant.dto import BriefState, RouterDecision

_AUDIENCE_RE = re.compile(r"(?P<size>\d{1,5})\s*(?:человек|гостей|гостя|гость)", re.I)


class HeuristicAssistantRouter:
    async def route(self, *, message: str, brief: BriefState) -> RouterDecision:
        normalized = _normalize_spaces(message)
        lower = normalized.lower()
        if not normalized or _is_too_ambiguous(lower):
            return _clarification_decision(brief)

        update = _brief_update_from_message(lower)
        missing_fields = _missing_fields(merge_brief(brief, update))

        if _looks_mixed(lower):
            event_type = update.event_type or brief.event_type or "мероприятия"
            audience_size = update.audience_size or brief.audience_size
            return RouterDecision(
                intent="mixed",
                confidence=0.88,
                known_facts=_known_facts(update),
                missing_fields=missing_fields,
                should_search_now=True,
                search_query=_mixed_search_query(event_type, audience_size),
                brief_update=_mixed_update(update),
            )

        if _looks_like_supplier_search(lower):
            search_query = _supplier_search_query(normalized)
            return RouterDecision(
                intent="supplier_search",
                confidence=0.84,
                known_facts=_known_facts(update),
                missing_fields=missing_fields,
                should_search_now=True,
                search_query=search_query,
                brief_update=_supplier_update(update, lower),
            )

        if _looks_like_brief_discovery(lower):
            return RouterDecision(
                intent="brief_discovery",
                confidence=0.82,
                known_facts=_known_facts(update),
                missing_fields=missing_fields,
                should_search_now=False,
                search_query=None,
                brief_update=update,
            )

        return _clarification_decision(brief)


def _normalize_spaces(value: str) -> str:
    return " ".join(value.strip().split())


def _is_too_ambiguous(lower: str) -> bool:
    return len(lower) < 12 or lower in {"подскажи", "помоги", "нужно", "хочу"}


def _looks_mixed(lower: str) -> bool:
    return ("помоги понять" in lower or "что нужно" in lower) and (
        "организ" in lower or "вечер" in lower or "мероприят" in lower
    )


def _looks_like_supplier_search(lower: str) -> bool:
    service_words = (
        "оборудован",
        "звук",
        "свет",
        "акустик",
        "сцен",
        "аренд",
        "поставщик",
        "цена",
        "стоимость",
    )
    request_words = ("нужно", "нужен", "нужна", "нужны", "найди", "подбери")
    return any(word in lower for word in service_words) and any(
        word in lower for word in request_words
    )


def _looks_like_brief_discovery(lower: str) -> bool:
    return ("хочу" in lower or "планир" in lower or "организ" in lower) and (
        "вечер" in lower or "корпоратив" in lower or "мероприят" in lower
    )


def _brief_update_from_message(lower: str) -> BriefState:
    return BriefState(
        event_type=_event_type(lower),
        audience_size=_audience_size(lower),
        required_services=_required_services(lower),
    )


def _event_type(lower: str) -> str | None:
    if "музыкаль" in lower and "вечер" in lower:
        return "музыкальный вечер"
    if "корпоратив" in lower:
        return "корпоратив"
    if "мероприят" in lower:
        return "мероприятие"
    return None


def _audience_size(lower: str) -> int | None:
    match = _AUDIENCE_RE.search(lower)
    if match is None:
        return None
    return int(match.group("size"))


def _required_services(lower: str) -> list[str]:
    if "музыкаль" in lower and "оборудован" in lower:
        return ["музыкальное оборудование"]
    services: list[str] = []
    if "звук" in lower or "акустик" in lower:
        services.append("звук")
    if "свет" in lower:
        services.append("свет")
    return services


def _mixed_update(update: BriefState) -> BriefState:
    services = update.required_services
    if not services and update.event_type == "музыкальный вечер":
        services = ["звук"]
    return BriefState(
        event_type=update.event_type,
        audience_size=update.audience_size,
        required_services=services,
    )


def _supplier_update(update: BriefState, lower: str) -> BriefState:
    services = update.required_services
    if not services and "оборудован" in lower:
        services = ["оборудование"]
    return BriefState(
        event_type=update.event_type,
        audience_size=update.audience_size,
        required_services=services,
    )


def _supplier_search_query(message: str) -> str:
    query = re.sub(
        r"^(?:мне\s+)?(?:нужно|нужен|нужна|нужны)\s+",
        "",
        message,
        flags=re.I,
    )
    return query.strip()


def _mixed_search_query(event_type: str, audience_size: int | None) -> str:
    if event_type == "музыкальный вечер":
        base = "музыкальное оборудование для музыкального вечера"
    else:
        base = f"оборудование для {event_type}"
    if audience_size is None:
        return base
    return f"{base} на {audience_size} человек"


def _missing_fields(brief: BriefState) -> list[str]:
    required = ["city", "audience_size", "venue_status"]
    return [field_name for field_name in required if getattr(brief, field_name) is None]


def _known_facts(brief: BriefState) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    for field_name in (
        "event_type",
        "city",
        "date_or_period",
        "audience_size",
        "venue",
        "venue_status",
        "duration_or_time_window",
        "budget",
        "event_level",
    ):
        value = getattr(brief, field_name)
        if value is not None:
            facts[field_name] = value
    for field_name in ("required_services", "constraints", "preferences"):
        value = getattr(brief, field_name)
        if value:
            facts[field_name] = value
    return facts


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
