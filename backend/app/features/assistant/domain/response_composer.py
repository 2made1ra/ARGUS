from __future__ import annotations

from app.features.assistant.dto import (
    ActionPlan,
    AssistantInterfaceMode,
    BriefState,
    FoundCatalogItem,
    Interpretation,
    RouterDecision,
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
    ) -> str:
        if decision.interface_mode == AssistantInterfaceMode.BRIEF_WORKSPACE:
            facts = _brief_fact_sentence(brief)
            questions = _question_sentence(decision.clarification_questions)
            if decision.should_search_now and found_items:
                return (
                    f"Обновил черновик брифа. {facts} "
                    "Нашел кандидатов в каталоге; карточки ниже являются "
                    f"предварительной выдачей. {questions}"
                ).strip()
            return (
                f"Начинаю собирать бриф мероприятия. {facts} {questions}"
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
        return (
            f"Обновил бриф и нашел кандидатов в каталоге. {facts} "
            f"Карточки ниже - предварительная выдача. {questions}"
        ).strip()
    if "update_brief" in interpretation.requested_actions:
        return f"Начинаю собирать бриф мероприятия. {facts} {questions}".strip()
    return f"Уточняю бриф мероприятия. {questions}".strip()


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


def _question_sentence(questions: list[str]) -> str:
    if not questions:
        return ""
    return " ".join(question for question in questions[:3])


__all__ = ["ResponseComposer"]
