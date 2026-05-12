from __future__ import annotations

from app.features.assistant.dto import BriefState

_SCALAR_FIELDS = (
    "event_type",
    "event_goal",
    "concept",
    "format",
    "city",
    "date_or_period",
    "audience_size",
    "venue",
    "venue_status",
    "duration_or_time_window",
    "budget",
    "budget_total",
    "budget_per_guest",
    "budget_notes",
    "catering_format",
    "event_level",
)

_LIST_FIELDS = (
    "venue_constraints",
    "technical_requirements",
    "required_services",
    "must_have_services",
    "nice_to_have_services",
    "selected_item_ids",
    "constraints",
    "preferences",
    "open_questions",
)


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

    values["service_needs"] = _merge_service_needs(
        current.service_needs,
        update.service_needs,
    )
    values["open_questions"] = _remove_answered_open_questions(
        values["open_questions"],
        values,
    )

    return BriefState(**values)


def _merge_unique(current: list[object], update: list[object]) -> list[object]:
    merged: list[object] = []
    seen: set[object] = set()
    for value in [*current, *update]:
        normalized = value.strip() if isinstance(value, str) else value
        if not normalized or normalized in seen:
            continue
        merged.append(normalized)
        seen.add(normalized)
    return merged


def _merge_service_needs(current: list[object], update: list[object]) -> list[object]:
    merged: list[object] = []
    seen: set[tuple[object, ...]] = set()
    for need in [*current, *update]:
        key = (
            getattr(need, "category", None),
            getattr(need, "priority", None),
            getattr(need, "source", None),
            getattr(need, "reason", None),
            getattr(need, "notes", None),
        )
        if key in seen:
            continue
        merged.append(need)
        seen.add(key)
    return merged


def _remove_answered_open_questions(
    open_questions: list[str],
    values: dict[str, object],
) -> list[str]:
    filtered: list[str] = []
    for field_name in open_questions:
        if field_name == "budget_total":
            answered = any(
                values.get(name) is not None
                for name in ("budget_total", "budget_per_guest", "budget_notes")
            )
        else:
            value = values.get(field_name)
            answered = value is not None and value != []
        if not answered:
            filtered.append(field_name)
    return filtered


__all__ = ["merge_brief"]
