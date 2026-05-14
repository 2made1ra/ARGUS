from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.features.assistant.domain.brief_renderer import BriefRenderer
from app.features.assistant.dto import (
    BriefState,
    CatalogItemDetail,
    FoundCatalogItem,
    MatchReason,
    ServiceNeed,
    SupplierVerificationResult,
)


def _detail(item_id: UUID) -> CatalogItemDetail:
    return CatalogItemDetail(
        id=item_id,
        name="Световой комплект",
        category="Свет",
        unit="день",
        unit_price=Decimal("15000.00"),
        supplier="ООО НИКА",
        supplier_inn="7701234567",
        supplier_city="Екатеринбург",
        supplier_phone=None,
        supplier_email=None,
        supplier_status=None,
        source_text="Световой комплект для корпоративного мероприятия",
    )


def _found_item(item_id: UUID, *, name: str = "Фуршет") -> FoundCatalogItem:
    return FoundCatalogItem(
        id=item_id,
        score=0.82,
        name=name,
        category="Кейтеринг",
        unit="гость",
        unit_price=Decimal("2500.00"),
        supplier="ООО Вкус",
        supplier_city="Екатеринбург",
        source_text_snippet="Фуршетное меню",
        source_text_full_available=True,
        match_reason=MatchReason(
            code="semantic",
            label="Семантическое совпадение с запросом",
        ),
    )


def _verification(item_id: UUID) -> SupplierVerificationResult:
    return SupplierVerificationResult(
        item_id=item_id,
        supplier_name="ООО НИКА",
        supplier_inn="7701234567",
        ogrn=None,
        legal_name="ООО НИКА",
        status="active",
        source="fake_registry",
        checked_at=None,
        risk_flags=[],
        message=None,
    )


def _section_items(rendered, title: str) -> list[str]:
    for section in rendered.sections:
        if section.title == title:
            return section.items
    raise AssertionError(f"section not found: {title}")


def test_renderer_outputs_all_required_sections_and_evidence() -> None:
    selected_id = UUID("11111111-1111-1111-1111-111111111111")
    unselected_id = UUID("22222222-2222-2222-2222-222222222222")
    brief = BriefState(
        event_type="корпоратив",
        event_goal="командное событие",
        concept="технологичная вечеринка",
        format="офлайн",
        city="Екатеринбург",
        date_or_period="май 2026",
        audience_size=120,
        venue_status="площадка выбрана",
        venue_constraints=["площадка без подвеса"],
        event_level="деловой комфорт",
        service_needs=[ServiceNeed(category="свет", priority="required")],
        required_services=["кейтеринг"],
        selected_item_ids=[selected_id],
        budget_total=2_000_000,
        budget_notes="без премиального сегмента",
        open_questions=["тайминг монтажа"],
    )

    rendered = BriefRenderer().render(
        brief=brief,
        selected_items=[_detail(selected_id)],
        found_items=[_found_item(unselected_id)],
        verification_results=[_verification(selected_id)],
    )

    assert [section.title for section in rendered.sections] == [
        "Основная информация",
        "Концепция и уровень",
        "Площадка и ограничения",
        "Блоки услуг",
        "Подборка кандидатов",
        "Проверка подрядчиков",
        "Бюджетные заметки",
        "Открытые вопросы",
    ]
    candidate_text = "\n".join(_section_items(rendered, "Подборка кандидатов"))
    assert "Световой комплект" in candidate_text
    assert "ООО НИКА" in candidate_text
    assert "15000.00" in candidate_text
    assert "Фуршет" not in candidate_text
    assert rendered.evidence == {
        "selected_item_ids": [str(selected_id)],
        "verification_result_ids": [str(selected_id)],
    }


def test_found_items_are_labeled_as_unselected_when_nothing_is_selected() -> None:
    found_id = UUID("33333333-3333-3333-3333-333333333333")
    rendered = BriefRenderer().render(
        brief=BriefState(
            event_type="корпоратив",
            city="Екатеринбург",
            selected_item_ids=[],
        ),
        selected_items=[],
        found_items=[_found_item(found_id, name="Фуршет на 120 гостей")],
        verification_results=[],
    )

    candidate_text = "\n".join(_section_items(rendered, "Подборка кандидатов"))
    assert "Кандидаты найдены, но не выбраны" in candidate_text
    assert "Фуршет на 120 гостей" in candidate_text
    assert rendered.evidence["selected_item_ids"] == []


def test_unknowns_go_to_open_questions_and_budget_does_not_sum_found_items() -> None:
    found_id = UUID("44444444-4444-4444-4444-444444444444")
    rendered = BriefRenderer().render(
        brief=BriefState(event_type="корпоратив", city="Екатеринбург"),
        selected_items=[],
        found_items=[_found_item(found_id)],
        verification_results=[],
    )

    assert "Дата или период мероприятия" in rendered.open_questions
    assert "Количество гостей" in rendered.open_questions
    assert "Статус площадки" in rendered.open_questions
    budget_text = "\n".join(_section_items(rendered, "Бюджетные заметки"))
    assert "2500.00" not in budget_text
    assert "найденных кандидатов" in budget_text
