from __future__ import annotations

from app.features.assistant.dto import (
    BriefState,
    CatalogItemDetail,
    FoundCatalogItem,
    RenderedBriefSection,
    RenderedEventBrief,
    SupplierVerificationResult,
)


class BriefRenderer:
    def render(
        self,
        *,
        brief: BriefState,
        selected_items: list[CatalogItemDetail],
        verification_results: list[SupplierVerificationResult],
        found_items: list[FoundCatalogItem] | None = None,
    ) -> RenderedEventBrief:
        candidate_items = found_items if found_items is not None else []
        open_questions = _open_questions(brief)
        sections = [
            _section(
                "Основная информация",
                [
                    _line("Тип", brief.event_type),
                    _line("Город", brief.city),
                    _line(
                        "Гостей",
                        str(brief.audience_size)
                        if brief.audience_size is not None
                        else None,
                    ),
                    _line("Дата или период", brief.date_or_period),
                ],
            ),
            _section(
                "Концепция и уровень",
                [
                    _line("Цель", brief.event_goal),
                    _line("Концепция", brief.concept),
                    _line("Формат", brief.format),
                    _line("Уровень", brief.event_level),
                ],
            ),
            _section(
                "Площадка и ограничения",
                [
                    _line("Площадка", brief.venue),
                    _line("Статус площадки", brief.venue_status),
                    *[f"Ограничение: {value}" for value in brief.venue_constraints],
                ],
            ),
            _section("Блоки услуг", _service_lines(brief)),
            _section(
                "Подборка кандидатов",
                _candidate_lines(
                    brief=brief,
                    selected_items=selected_items,
                    found_items=candidate_items,
                ),
            ),
            _section(
                "Проверка подрядчиков",
                _verification_lines(verification_results),
            ),
            _section(
                "Бюджетные заметки",
                _budget_lines(
                    brief=brief,
                    found_items=candidate_items,
                ),
            ),
            _section(
                "Открытые вопросы",
                open_questions if open_questions else ["Нет"],
            ),
        ]
        return RenderedEventBrief(
            title="Бриф мероприятия",
            sections=sections,
            open_questions=open_questions,
            evidence={
                "selected_item_ids": _selected_item_evidence(
                    brief=brief,
                    selected_items=selected_items,
                ),
                "verification_result_ids": _verification_evidence(
                    verification_results,
                ),
            },
        )


def _section(title: str, items: list[str | None]) -> RenderedBriefSection:
    cleaned = [item for item in items if item]
    return RenderedBriefSection(title=title, items=cleaned if cleaned else ["Нет"])


def _line(label: str, value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return f"{label}: {value}"


def _service_lines(brief: BriefState) -> list[str]:
    lines: list[str] = []
    lines.extend(f"Обязательный блок: {value}" for value in brief.must_have_services)
    lines.extend(f"Нужен блок: {value}" for value in brief.required_services)
    lines.extend(f"Опционально: {value}" for value in brief.nice_to_have_services)
    for need in brief.service_needs:
        lines.append(f"{need.category}: {need.priority}")
    return lines


def _candidate_lines(
    *,
    brief: BriefState,
    selected_items: list[CatalogItemDetail],
    found_items: list[FoundCatalogItem],
) -> list[str]:
    selected_ids = set(brief.selected_item_ids)
    lines = [_selected_detail_line(item) for item in selected_items]
    selected_detail_ids = {item.id for item in selected_items}
    selected_found_items = [
        item
        for item in found_items
        if item.id in selected_ids and item.id not in selected_detail_ids
    ]
    lines.extend(_selected_found_item_line(item) for item in selected_found_items)
    if lines:
        return lines
    if selected_ids:
        return [
            "Выбранные item_id переданы, но детализация каталога не загружена: "
            + ", ".join(str(item_id) for item_id in brief.selected_item_ids)
        ]
    if found_items:
        return [
            "Кандидаты найдены, но не выбраны: " + _found_item_fact_line(item)
            for item in found_items
        ]
    return ["Выбранные позиции пока не добавлены"]


def _selected_detail_line(item: CatalogItemDetail) -> str:
    return "Выбрано: " + "; ".join(
        part
        for part in (
            item.name,
            _labeled("категория", item.category),
            _labeled("поставщик", item.supplier),
            _labeled("город", item.supplier_city),
            _price_line(unit_price=item.unit_price, unit=item.unit),
        )
        if part is not None
    )


def _selected_found_item_line(item: FoundCatalogItem) -> str:
    return "Выбрано: " + _found_item_fact_line(item)


def _found_item_fact_line(item: FoundCatalogItem) -> str:
    return "; ".join(
        part
        for part in (
            item.name,
            _labeled("категория", item.category),
            _labeled("поставщик", item.supplier),
            _labeled("город", item.supplier_city),
            _price_line(unit_price=item.unit_price, unit=item.unit),
        )
        if part is not None
    )


def _verification_lines(
    verification_results: list[SupplierVerificationResult],
) -> list[str]:
    if not verification_results:
        return ["Проверка подрядчиков еще не выполнялась"]
    return [
        "; ".join(
            part
            for part in (
                _labeled("поставщик", result.supplier_name),
                _labeled("ИНН", result.supplier_inn),
                _verification_status_line(result),
                _labeled("источник", result.source),
                _risk_flags_line(result.risk_flags),
            )
            if part is not None
        )
        for result in verification_results
    ]


def _budget_lines(
    *,
    brief: BriefState,
    found_items: list[FoundCatalogItem],
) -> list[str]:
    lines: list[str] = []
    if brief.budget_total is not None:
        lines.append(f"Общий бюджет: {brief.budget_total}")
    if brief.budget_per_guest is not None:
        lines.append(f"На гостя: {brief.budget_per_guest}")
    if brief.budget_notes is not None:
        lines.append(f"Комментарий: {brief.budget_notes}")
    if brief.selected_item_ids:
        lines.append(
            "По выбранным позициям нужны количества; итоговую сумму не считаю."
        )
    elif found_items:
        lines.append(
            "Смету из найденных кандидатов не считаю без выбранных позиций "
            "и количеств."
        )
    return lines


def _open_questions(brief: BriefState) -> list[str]:
    questions = [_question_label(value) for value in brief.open_questions]
    if brief.event_type is None:
        questions.append("Тип мероприятия")
    if brief.city is None:
        questions.append("Город")
    if brief.date_or_period is None:
        questions.append("Дата или период мероприятия")
    if brief.audience_size is None:
        questions.append("Количество гостей")
    if brief.venue_status is None:
        questions.append("Статус площадки")
    if brief.concept is None and brief.event_level is None:
        questions.append("Концепция или уровень мероприятия")
    if (
        brief.budget_total is None
        and brief.budget_per_guest is None
        and brief.budget_notes is None
    ):
        questions.append("Бюджет или уровень затрат")
    if not (
        brief.service_needs
        or brief.required_services
        or brief.must_have_services
        or brief.nice_to_have_services
    ):
        questions.append("Блоки услуг для подбора")
    return _dedupe(questions)


def _question_label(value: str) -> str:
    return _OPEN_QUESTION_LABELS.get(value, value)


def _selected_item_evidence(
    *,
    brief: BriefState,
    selected_items: list[CatalogItemDetail],
) -> list[str]:
    return _dedupe(
        [
            *[str(item_id) for item_id in brief.selected_item_ids],
            *[str(item.id) for item in selected_items],
        ],
    )


def _verification_evidence(
    verification_results: list[SupplierVerificationResult],
) -> list[str]:
    return _dedupe(
        [
            str(result.item_id)
            for result in verification_results
            if result.item_id is not None
        ],
    )


def _labeled(label: str, value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return f"{label}: {value}"


def _price_line(*, unit_price: object, unit: str) -> str:
    return f"цена: {unit_price} за {unit}"


def _verification_status_line(result: SupplierVerificationResult) -> str:
    if result.status == "active":
        return "статус: юрлицо найдено как действующее в проверочном источнике"
    return f"статус: {result.status}"


def _risk_flags_line(risk_flags: list[str]) -> str | None:
    if not risk_flags:
        return None
    return "риск-флаги: " + ", ".join(risk_flags)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


_OPEN_QUESTION_LABELS = {
    "event_type": "Тип мероприятия",
    "event_goal": "Цель мероприятия",
    "concept": "Концепция мероприятия",
    "format": "Формат мероприятия",
    "city": "Город",
    "date_or_period": "Дата или период мероприятия",
    "audience_size": "Количество гостей",
    "venue": "Площадка",
    "venue_status": "Статус площадки",
    "budget_total": "Бюджет или уровень затрат",
    "budget_per_guest": "Бюджет на гостя",
    "required_services": "Блоки услуг для подбора",
}


__all__ = ["BriefRenderer"]
