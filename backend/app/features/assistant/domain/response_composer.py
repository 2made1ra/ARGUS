from __future__ import annotations

from app.features.assistant.dto import (
    ActionPlan,
    AssistantInterfaceMode,
    BriefState,
    CatalogItemDetail,
    FoundCatalogItem,
    Interpretation,
    RenderedEventBrief,
    RouterDecision,
    SupplierVerificationResult,
)


class ResponseComposer:
    def compose(
        self,
        *,
        interpretation: Interpretation,
        action_plan: ActionPlan,
        brief: BriefState,
        found_items: list[FoundCatalogItem],
    ) -> str:
        if action_plan.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE:
            return _brief_workspace_message(
                interpretation=interpretation,
                action_plan=action_plan,
                brief=brief,
                found_items=found_items,
            )
        return _chat_search_message(
            action_plan=action_plan,
            found_items=found_items,
        )

    def compose_from_decision(
        self,
        *,
        decision: RouterDecision,
        brief: BriefState,
        found_items: list[FoundCatalogItem],
        verification_results: list[SupplierVerificationResult] | None = None,
        item_details: list[CatalogItemDetail] | None = None,
        rendered_brief: RenderedEventBrief | None = None,
    ) -> str:
        if decision.intent == "render_brief":
            return _render_message_from_decision(
                decision=decision,
                rendered_brief=rendered_brief,
            )
        if decision.intent == "verification":
            return _verification_message_from_decision(
                decision=decision,
                verification_results=verification_results or [],
            )
        if decision.intent == "selection":
            return _selection_message_from_decision(decision=decision, brief=brief)
        if decision.intent == "comparison":
            return _comparison_message_from_decision(
                decision=decision,
                item_details=item_details or [],
            )
        if decision.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE:
            facts = _brief_fact_sentence(brief)
            questions = _question_sentence(decision.clarification_questions)
            if decision.should_search_now and found_items:
                search_prefix = (
                    "Обновил бриф и нашел кандидатов в каталоге."
                    if _has_brief_update(decision.brief_update)
                    else "Нашел кандидатов в каталоге по текущему брифу."
                )
                return (
                    f"{search_prefix} {facts} "
                    f"Карточки ниже являются предварительной выдачей. {questions}"
                ).strip()
            if decision.should_search_now:
                return (
                    f"По текущему брифу в каталоге нет строк. {facts} "
                    f"{questions}"
                ).strip()
            if _has_brief_update(decision.brief_update):
                prefix = (
                    "Обновил бриф мероприятия."
                    if _has_existing_brief_context(
                        brief=brief,
                        update=decision.brief_update,
                    )
                    else "Начинаю собирать бриф мероприятия."
                )
                return f"{prefix} {facts} {questions}".strip()
            return (
                f"Уточняю бриф мероприятия. {facts} {questions}"
            ).strip()
        return _chat_search_message_from_decision(decision, found_items)


def _brief_workspace_message(
    *,
    interpretation: Interpretation,
    action_plan: ActionPlan,
    brief: BriefState,
    found_items: list[FoundCatalogItem],
) -> str:
    facts = _brief_fact_sentence(brief)
    questions = _question_sentence(action_plan.clarification_questions)
    if action_plan.should_search_now and found_items:
        search_prefix = (
            "Обновил бриф и нашел кандидатов в каталоге."
            if _has_brief_update(interpretation.brief_update)
            else "Нашел кандидатов в каталоге по текущему брифу."
        )
        return (
            f"{search_prefix} {facts} "
            f"Карточки ниже - предварительная выдача. {questions}"
        ).strip()
    if action_plan.should_search_now:
        return (
            f"По текущему брифу в каталоге нет строк. {facts} {questions}"
        ).strip()
    if "update_brief" in interpretation.requested_actions:
        prefix = (
            "Обновил бриф мероприятия."
            if _has_existing_brief_context(
                brief=brief,
                update=interpretation.brief_update,
            )
            else "Начинаю собирать бриф мероприятия."
        )
        return f"{prefix} {facts} {questions}".strip()
    return f"Уточняю бриф мероприятия. {facts} {questions}".strip()


def _chat_search_message(
    *,
    action_plan: ActionPlan,
    found_items: list[FoundCatalogItem],
) -> str:
    if action_plan.should_search_now and found_items:
        return (
            "Нашел кандидатов в каталоге. Карточки ниже - предварительная "
            "выдача по вашему запросу."
        )
    if action_plan.should_search_now and not found_items:
        return (
            "В каталоге нет строк по этому запросу. Уточните услугу, город, "
            "формат задачи или ценовой диапазон, и я попробую сузить поиск."
        )
    questions = _question_sentence(action_plan.clarification_questions)
    return f"Уточните параметры поиска. {questions}".strip()


def _chat_search_message_from_decision(
    decision: RouterDecision,
    found_items: list[FoundCatalogItem],
) -> str:
    if decision.should_search_now and found_items:
        return (
            "Нашел кандидатов в каталоге. Конкретные строки, цены и поставщики "
            "остаются в found_items; это кандидаты для проверки, а не выбранные "
            "позиции сметы."
        )
    if decision.should_search_now and not found_items:
        return (
            "В каталоге нет строк по этому запросу. Уточните услугу, категорию, "
            "город, поставщика или ИНН, и я попробую сузить поиск."
        )
    questions = _question_sentence(decision.clarification_questions)
    return f"Уточните параметры поиска. {questions}".strip()


def _verification_message_from_decision(
    *,
    decision: RouterDecision,
    verification_results: list[SupplierVerificationResult],
) -> str:
    questions = _question_sentence(decision.clarification_questions)
    if "candidate_context" in decision.missing_fields:
        return f"Уточните, каких найденных подрядчиков проверить. {questions}".strip()
    if verification_results:
        return (
            "Проверил поставщиков по доступным ИНН из переданных строк каталога. "
            "Юридические статусы и риск-флаги вернул отдельно в "
            "verification_results; status=active означает только действующее "
            "юрлицо в проверочном источнике."
        )
    return (
        "Не получил проверяемых результатов по переданным позициям. "
        "Проверьте, что item id есть в каталоге и содержит данные поставщика."
    )


def _selection_message_from_decision(
    *,
    decision: RouterDecision,
    brief: BriefState,
) -> str:
    questions = _question_sentence(decision.clarification_questions)
    if "candidate_context" in decision.missing_fields:
        return f"Уточните, какой вариант добавить в подборку. {questions}".strip()
    if brief.selected_item_ids:
        return (
            "Добавил выбранный вариант в selected_item_ids. "
            "Найденные карточки остаются кандидатами, пока пользователь явно "
            "не добавит их в подборку."
        )
    return (
        "Не удалось связать вариант с видимой карточкой. "
        "Передайте visible_candidates."
    )


def _comparison_message_from_decision(
    *,
    decision: RouterDecision,
    item_details: list[CatalogItemDetail],
) -> str:
    questions = _question_sentence(decision.clarification_questions)
    if "candidate_context" in decision.missing_fields:
        return f"Уточните, какие две позиции сравнить. {questions}".strip()
    if len(item_details) < 2:
        return (
            "Не удалось загрузить две позиции для сравнения. Проверьте, что "
            "видимые карточки есть в каталоге."
        )
    first, second = item_details[:2]
    return (
        "Сравнил две позиции по полям карточек каталога. "
        f"1) {_comparison_line(first)}. "
        f"2) {_comparison_line(second)}. "
        "Это кандидаты из каталога, не выбранные позиции сметы."
    )


def _render_message_from_decision(
    *,
    decision: RouterDecision,
    rendered_brief: RenderedEventBrief | None,
) -> str:
    if rendered_brief is not None:
        return "Подготовил структурированный бриф.\n\n" + _rendered_brief_text(
            rendered_brief,
        )
    questions = _question_sentence(decision.clarification_questions)
    if questions:
        return f"Пока не из чего сформировать итоговый бриф. {questions}".strip()
    return "Пока не из чего сформировать итоговый бриф."


def _brief_fact_sentence(brief: BriefState) -> str:
    facts: list[str] = []
    if brief.event_type is not None:
        facts.append(brief.event_type)
    if brief.city is not None:
        facts.append(brief.city)
    if brief.audience_size is not None:
        facts.append(f"{brief.audience_size} гостей")
    if not facts:
        return ""
    return "Уже зафиксировал: " + ", ".join(facts) + "."


def _has_brief_update(update: BriefState) -> bool:
    return any(
        (
            update.event_type,
            update.event_goal,
            update.concept,
            update.format,
            update.city,
            update.date_or_period,
            update.audience_size,
            update.venue,
            update.venue_status,
            update.venue_constraints,
            update.duration_or_time_window,
            update.event_level,
            update.budget,
            update.budget_total,
            update.budget_per_guest,
            update.budget_notes,
            update.catering_format,
            update.technical_requirements,
            update.service_needs,
            update.required_services,
            update.must_have_services,
            update.nice_to_have_services,
            update.constraints,
            update.preferences,
        )
    )


def _has_existing_brief_context(*, brief: BriefState, update: BriefState) -> bool:
    scalar_fields = (
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
        "event_level",
        "budget",
        "budget_total",
        "budget_per_guest",
        "budget_notes",
        "catering_format",
    )
    for field_name in scalar_fields:
        if (
            getattr(brief, field_name) is not None
            and getattr(update, field_name) is None
        ):
            return True

    list_fields = (
        "venue_constraints",
        "technical_requirements",
        "service_needs",
        "required_services",
        "must_have_services",
        "nice_to_have_services",
        "constraints",
        "preferences",
        "selected_item_ids",
    )
    for field_name in list_fields:
        current_values = getattr(brief, field_name)
        update_values = getattr(update, field_name)
        if current_values and not update_values:
            return True
    return False


def _rendered_brief_text(rendered_brief: RenderedEventBrief) -> str:
    lines = [rendered_brief.title]
    has_open_questions_section = False
    for section in rendered_brief.sections:
        if section.title == "Открытые вопросы":
            has_open_questions_section = True
        lines.append("")
        lines.append(section.title)
        lines.extend(f"- {item}" for item in section.items)
    if rendered_brief.open_questions and not has_open_questions_section:
        lines.append("")
        lines.append("Открытые вопросы")
        lines.extend(f"- {question}" for question in rendered_brief.open_questions)
    return "\n".join(lines)


def _question_sentence(questions: list[str]) -> str:
    if not questions:
        return ""
    return " ".join(question for question in questions[:3])


def _comparison_line(detail: CatalogItemDetail) -> str:
    parts = [
        detail.name,
        f"{detail.unit_price} за {detail.unit}",
    ]
    if detail.supplier is not None:
        parts.append(detail.supplier)
    if detail.supplier_city is not None:
        parts.append(detail.supplier_city)
    if detail.category is not None:
        parts.append(detail.category)
    return ", ".join(parts)


__all__ = ["ResponseComposer"]
