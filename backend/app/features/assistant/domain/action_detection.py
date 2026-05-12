from __future__ import annotations

import re
from dataclasses import dataclass

from app.features.assistant.domain.taxonomy import (
    BRIEF_CREATION_PHRASES,
    CONTEXTUAL_BRIEF_PHRASES,
    DIRECT_SEARCH_PHRASES,
    SEARCH_NOUNS,
    service_categories_for,
)
from app.features.assistant.dto import BriefState


@dataclass(frozen=True, slots=True)
class ActionSignals:
    event_creation: bool
    direct_catalog_search: bool
    contextual_brief_update: bool


def detect_action_signals(message: str, brief: BriefState) -> ActionSignals:
    lower = " ".join(message.strip().lower().split())
    service_categories = service_categories_for(lower)
    event_creation = _has_event_creation_signal(lower)
    direct_catalog_search = _has_direct_search_signal(
        lower,
        service_categories,
        event_creation=event_creation,
    )
    contextual_brief_update = _has_active_brief(brief) and any(
        phrase in lower for phrase in CONTEXTUAL_BRIEF_PHRASES
    )

    return ActionSignals(
        event_creation=event_creation,
        direct_catalog_search=direct_catalog_search,
        contextual_brief_update=contextual_brief_update,
    )


def _has_event_creation_signal(lower: str) -> bool:
    if "собери бриф" in lower or "собрать бриф" in lower:
        return True
    if _has_needed_event_phrase(lower):
        return True
    if any(phrase in lower for phrase in BRIEF_CREATION_PHRASES):
        return any(
            word in lower
            for word in (
                "корпоратив",
                "мероприят",
                "конференц",
                "презентац",
                "вечер",
            )
        )
    return False


def _has_needed_event_phrase(lower: str) -> bool:
    return re.search(
        r"\bнуж(?:ен|на|но|ны)\s+"
        r"(?:корпоратив|корпоративный|конференц\w*|мероприят\w*|"
        r"презентац\w*|вечер)\b",
        lower,
    ) is not None


def _has_direct_search_signal(
    lower: str,
    service_categories: list[str],
    *,
    event_creation: bool,
) -> bool:
    has_search_phrase = any(phrase in lower for phrase in DIRECT_SEARCH_PHRASES)
    has_search_noun = any(noun in lower for noun in SEARCH_NOUNS)
    has_need_service = any(
        phrase in lower
        for phrase in ("нужен ", "нужна ", "нужны ", "нужно ")
    ) and bool(service_categories) and not event_creation
    has_search_target = has_search_noun or bool(service_categories)
    return (has_search_phrase and has_search_target) or (
        has_search_noun and bool(service_categories)
    ) or has_need_service


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
        )
    )


__all__ = ["ActionSignals", "detect_action_signals"]
