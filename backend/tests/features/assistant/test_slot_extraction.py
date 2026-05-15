from __future__ import annotations

from app.features.assistant.domain.slot_extraction import extract_event_brief_slots


def test_extracts_event_intake_slots_without_service_search() -> None:
    slots = extract_event_brief_slots(
        "Нужно организовать корпоратив на 120 человек в Екатеринбурге"
    )

    assert slots.event_type == "корпоратив"
    assert slots.city == "Екатеринбург"
    assert slots.audience_size == 120
    assert slots.service_needs == []
    assert slots.required_services == []


def test_extracts_budget_venue_constraints_and_technical_requirements() -> None:
    slots = extract_event_brief_slots(
        "Площадка уже есть, монтаж только ночью, бюджет около 2 млн, "
        "площадка без подвеса"
    )

    assert slots.venue_status == "площадка есть"
    assert slots.budget_total == 2_000_000
    assert slots.venue_constraints == ["площадка без подвеса"]
    assert slots.technical_requirements == ["монтаж только ночью"]


def test_extracts_budget_words_event_level_and_negative_concept() -> None:
    slots = extract_event_brief_slots(
        "Площадки нет, по бюджету 1 миллион, уровень светский, "
        "концепции не планируется"
    )

    assert slots.venue_status == "площадки нет"
    assert slots.budget_total == 1_000_000
    assert slots.event_level == "светский"
    assert slots.concept == "не планируется"


def test_extracts_sports_inventory_as_specific_service_need() -> None:
    slots = extract_event_brief_slots("мне нужен спортивный инвентарь")

    assert [need.category for need in slots.service_needs] == [
        "спортивный инвентарь",
    ]
    assert slots.required_services == ["спортивный инвентарь"]


def test_extracts_per_guest_budget_catering_format_and_service_need() -> None:
    slots = extract_event_brief_slots(
        "На 120 человек в Екатеринбурге нужен кейтеринг фуршет до 2500 на гостя"
    )

    assert slots.city == "Екатеринбург"
    assert slots.audience_size == 120
    assert slots.budget_per_guest == 2500
    assert slots.catering_format == "фуршет"
    assert slots.required_services == ["кейтеринг"]
    assert [need.category for need in slots.service_needs] == ["кейтеринг"]


def test_extracts_concept_goal_format_and_date() -> None:
    slots = extract_event_brief_slots(
        "Собери бриф на конференцию 15 июня, формат гибрид, "
        "цель презентация продукта, концепция технологичная"
    )

    assert slots.event_type == "конференция"
    assert slots.date_or_period == "15 июня"
    assert slots.format == "гибрид"
    assert slots.event_goal == "презентация продукта"
    assert slots.concept == "технологичная"
