from __future__ import annotations

from app.features.assistant.dto import BriefState

_SCALAR_FIELDS = (
    "event_type",
    "city",
    "date_or_period",
    "audience_size",
    "venue",
    "venue_status",
    "duration_or_time_window",
    "budget",
    "event_level",
)

_LIST_FIELDS = ("required_services", "constraints", "preferences")


def merge_brief(current: BriefState, update: BriefState) -> BriefState:
    values: dict[str, object] = {}

    for field_name in _SCALAR_FIELDS:
        update_value = getattr(update, field_name)
        values[field_name] = (
            update_value if update_value is not None else getattr(current, field_name)
        )

    for field_name in _LIST_FIELDS:
        values[field_name] = _merge_unique(
            getattr(current, field_name),
            getattr(update, field_name),
        )

    return BriefState(**values)


def _merge_unique(current: list[str], update: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in [*current, *update]:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        merged.append(normalized)
        seen.add(normalized)
    return merged


__all__ = ["merge_brief"]
