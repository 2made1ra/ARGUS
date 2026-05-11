from __future__ import annotations

from uuid import uuid4

from app.features.assistant.brief import merge_brief
from app.features.assistant.dto import (
    AssistantChatRequest,
    AssistantChatResponse,
    BriefState,
    FoundCatalogItem,
    RouterDecision,
)
from app.features.assistant.ports import AssistantRouter, CatalogSearchTool

_DEFAULT_SEARCH_LIMIT = 10


class ChatTurnUseCase:
    def __init__(
        self,
        *,
        router: AssistantRouter,
        catalog_search: CatalogSearchTool,
    ) -> None:
        self._router = router
        self._catalog_search = catalog_search

    async def execute(self, request: AssistantChatRequest) -> AssistantChatResponse:
        current_brief = request.brief if request.brief is not None else BriefState()
        decision = await self._router.route(
            message=request.message,
            brief=current_brief,
        )
        brief = merge_brief(current_brief, decision.brief_update)
        found_items = await self._search_if_needed(decision)
        return AssistantChatResponse(
            session_id=request.session_id or uuid4(),
            message=_message_for(decision, found_items),
            router=decision,
            brief=brief,
            found_items=found_items,
        )

    async def _search_if_needed(
        self,
        decision: RouterDecision,
    ) -> list[FoundCatalogItem]:
        if not decision.should_search_now or decision.search_query is None:
            return []
        return await self._catalog_search.search_items(
            query=decision.search_query,
            limit=_DEFAULT_SEARCH_LIMIT,
        )


def _message_for(
    decision: RouterDecision,
    found_items: list[FoundCatalogItem],
) -> str:
    if decision.should_search_now and not found_items:
        return (
            "В каталоге нет строк по этому запросу. Уточните услугу, категорию, "
            "город, поставщика или ИНН, и я попробую сузить поиск."
        )

    if decision.intent == "brief_discovery":
        return (
            "Собрал черновик брифа по вашему сообщению. Чтобы двигаться точнее, "
            f"уточните: {_questions_for(decision.missing_fields)}."
        )

    if decision.intent == "supplier_search":
        return (
            "Нашел кандидатов в каталоге. Конкретные строки, цены и поставщики "
            "остаются в found_items; это кандидаты для проверки, а не выбранные "
            "позиции сметы. Можно уточнить город, дату, формат площадки или бюджет."
        )

    if decision.intent == "mixed":
        return (
            "Обновил черновик брифа и запустил поиск по очевидной потребности. "
            "Проверяемые карточки находятся в found_items; это кандидаты, а не "
            "готовые строки коммерческого предложения. Следом можно уточнить "
            "город, площадку и бюджет."
        )

    return (
        "Уточните, пожалуйста, что нужно сделать: собрать бриф, найти позиции "
        "в каталоге или совместить оба шага."
    )


def _questions_for(missing_fields: list[str]) -> str:
    labels = {
        "city": "город",
        "audience_size": "количество гостей",
        "venue_status": "есть ли площадка",
        "date_or_period": "дату или период",
        "budget": "ориентир по бюджету",
    }
    fields = [labels.get(field, field) for field in missing_fields[:5]]
    if not fields:
        return "какая следующая задача приоритетна"
    return ", ".join(fields)


__all__ = ["ChatTurnUseCase"]
