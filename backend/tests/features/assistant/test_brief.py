from __future__ import annotations

from app.features.assistant.brief import merge_brief
from app.features.assistant.dto import BriefState


def test_empty_update_keeps_unknown_values_empty() -> None:
    merged = merge_brief(BriefState(), BriefState())

    assert merged == BriefState()
    assert merged.required_services == []
    assert merged.constraints == []
    assert merged.preferences == []


def test_null_update_values_do_not_overwrite_existing_scalars() -> None:
    current = BriefState(
        event_type="музыкальный вечер",
        city="Москва",
        audience_size=100,
        budget="до 500000",
    )

    merged = merge_brief(
        current,
        BriefState(event_type=None, city=None, audience_size=None, budget=None),
    )

    assert merged.event_type == "музыкальный вечер"
    assert merged.city == "Москва"
    assert merged.audience_size == 100
    assert merged.budget == "до 500000"


def test_non_null_update_values_overwrite_scalars() -> None:
    current = BriefState(
        event_type="музыкальный вечер",
        city="Москва",
        audience_size=80,
    )

    merged = merge_brief(
        current,
        BriefState(
            event_type="корпоратив",
            city="Екатеринбург",
            audience_size=120,
        ),
    )

    assert merged.event_type == "корпоратив"
    assert merged.city == "Екатеринбург"
    assert merged.audience_size == 120


def test_merges_arrays_without_duplicates_and_preserves_order() -> None:
    current = BriefState(
        required_services=["звук"],
        constraints=["без алкоголя"],
        preferences=["живой вокал"],
    )

    merged = merge_brief(
        current,
        BriefState(
            required_services=["звук", "свет"],
            constraints=["без алкоголя", "центр города"],
            preferences=["живой вокал", "премиальный уровень"],
        ),
    )

    assert merged.required_services == ["звук", "свет"]
    assert merged.constraints == ["без алкоголя", "центр города"]
    assert merged.preferences == ["живой вокал", "премиальный уровень"]


def test_merges_phase_four_brief_fields() -> None:
    current = BriefState()

    merged = merge_brief(
        current,
        BriefState(
            venue_status="площадка есть",
            duration_or_time_window="вечер, 4 часа",
            event_level="средний",
        ),
    )

    assert merged.venue_status == "площадка есть"
    assert merged.duration_or_time_window == "вечер, 4 часа"
    assert merged.event_level == "средний"
