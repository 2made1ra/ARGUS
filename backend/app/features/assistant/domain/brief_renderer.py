from __future__ import annotations

from app.features.assistant.dto import (
    BriefState,
    CatalogItemDetail,
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
    ) -> RenderedEventBrief:
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
            _section("Подборка кандидатов", _selected_item_lines(selected_items)),
            _section(
                "Проверка подрядчиков",
                _verification_lines(verification_results),
            ),
            _section("Бюджетные заметки", _budget_lines(brief)),
            _section(
                "Открытые вопросы",
                list(brief.open_questions) if brief.open_questions else ["Нет"],
            ),
        ]
        return RenderedEventBrief(
            title="Бриф мероприятия",
            sections=sections,
            open_questions=list(brief.open_questions),
            evidence={
                "selected_item_ids": [str(item.id) for item in selected_items],
                "verification_result_ids": [
                    str(result.item_id)
                    for result in verification_results
                    if result.item_id is not None
                ],
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


def _selected_item_lines(selected_items: list[CatalogItemDetail]) -> list[str]:
    if not selected_items:
        return ["Выбранные позиции пока не добавлены"]
    return [
        " / ".join(
            part
            for part in (item.name, item.supplier, item.supplier_city)
            if part is not None
        )
        for item in selected_items
    ]


def _verification_lines(
    verification_results: list[SupplierVerificationResult],
) -> list[str]:
    if not verification_results:
        return ["Проверка подрядчиков еще не выполнялась"]
    return [
        " / ".join(
            part
            for part in (
                result.supplier_name,
                result.supplier_inn,
                result.status,
            )
            if part is not None
        )
        for result in verification_results
    ]


def _budget_lines(brief: BriefState) -> list[str]:
    lines: list[str] = []
    if brief.budget_total is not None:
        lines.append(f"Общий бюджет: {brief.budget_total}")
    if brief.budget_per_guest is not None:
        lines.append(f"На гостя: {brief.budget_per_guest}")
    if brief.budget_notes is not None:
        lines.append(f"Комментарий: {brief.budget_notes}")
    return lines


__all__ = ["BriefRenderer"]
