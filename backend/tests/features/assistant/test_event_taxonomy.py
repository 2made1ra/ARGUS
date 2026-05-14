from __future__ import annotations

from app.features.assistant.domain.slot_extraction import extract_event_brief_slots
from app.features.assistant.domain.taxonomy import (
    canonical_city_for,
    service_categories_for,
)


def test_service_taxonomy_covers_core_event_blocks_and_professional_aliases() -> None:
    cases = {
        "звук": "звук",
        "радики": "звук",
        "свет": "свет",
        "фермы": "сценические конструкции",
        "экран": "мультимедиа",
        "кейтеринг": "кейтеринг",
        "welcome-зона": "welcome-зона",
        "хостес": "персонал",
        "логистика": "логистика",
        "декор": "декор",
        "мебель": "мебель",
        "площадка": "площадка",
    }

    for phrase, category in cases.items():
        assert category in service_categories_for(phrase)

    assert canonical_city_for("в Екате") == "Екатеринбург"


def test_welcome_zone_expands_to_normalized_service_bundle() -> None:
    slots = extract_event_brief_slots("надо закрыть welcome-зону")

    needs_by_category = {need.category: need for need in slots.service_needs}
    bundle_categories = {
        "персонал",
        "мебель",
        "декор",
        "мультимедиа",
        "кейтеринг",
    }
    assert slots.required_services == ["welcome-зона"]
    assert slots.must_have_services == []
    assert "welcome-зона" in needs_by_category
    assert bundle_categories <= set(needs_by_category)
    for category in bundle_categories:
        assert needs_by_category[category].source == "policy_inferred"
        assert needs_by_category[category].priority == "nice_to_have"
    assert needs_by_category["персонал"].reason == "welcome-зона"
    assert slots.nice_to_have_services == [
        "мебель",
        "персонал",
        "декор",
        "мультимедиа",
        "кейтеринг",
    ]


def test_no_rigging_constraint_creates_policy_inferred_service_needs() -> None:
    slots = extract_event_brief_slots(
        "Площадка без подвеса, нужен корпоратив на 300 человек"
    )

    inferred = {
        need.category: need
        for need in slots.service_needs
        if need.source == "policy_inferred"
    }
    assert slots.event_type == "корпоратив"
    assert slots.audience_size == 300
    assert slots.venue_constraints == ["площадка без подвеса"]
    assert set(inferred) == {"сценические конструкции", "свет", "мультимедиа"}
    assert all(need.priority == "nice_to_have" for need in inferred.values())
    assert all(need.reason == "площадка без подвеса" for need in inferred.values())
    assert "ground support" in (inferred["сценические конструкции"].notes or "")
    assert "напольные" in (inferred["свет"].notes or "")
    assert slots.required_services == []
    assert slots.must_have_services == []
    assert slots.nice_to_have_services == [
        "сценические конструкции",
        "свет",
        "мультимедиа",
    ]


def test_service_priority_lists_are_separated_from_preferences() -> None:
    slots = extract_event_brief_slots(
        "Обязательно нужен звук, хорошо бы декор, без премиума"
    )

    priorities = {need.category: need.priority for need in slots.service_needs}
    assert priorities["звук"] == "must_have"
    assert priorities["декор"] == "nice_to_have"
    assert slots.required_services == []
    assert slots.must_have_services == ["звук"]
    assert slots.nice_to_have_services == ["декор"]
    assert slots.technical_requirements == []
    assert slots.venue_constraints == []
    assert slots.constraints == []
    assert slots.preferences == ["без премиума"]
