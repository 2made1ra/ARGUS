from __future__ import annotations

from uuid import uuid4

from app.features.assistant.brief import merge_brief
from app.features.assistant.domain.response_composer import ResponseComposer
from app.features.assistant.dto import (
    ActionPlan,
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
            recent_turns=list(request.recent_turns),
            visible_candidates=list(request.visible_candidates),
        )
        brief = (
            merge_brief(current_brief, decision.brief_update)
            if _should_update_brief(decision)
            else current_brief
        )
        found_items = await self._search_if_needed(decision)
        action_plan = _action_plan_from_decision(decision)
        return AssistantChatResponse(
            session_id=request.session_id or uuid4(),
            message=ResponseComposer().compose_from_decision(
                decision=decision,
                brief=brief,
                found_items=found_items,
            ),
            router=decision,
            brief=brief,
            found_items=found_items,
            ui_mode=decision.interface_mode,
            action_plan=action_plan,
        )

    async def _search_if_needed(
        self,
        decision: RouterDecision,
    ) -> list[FoundCatalogItem]:
        if not decision.should_search_now:
            return []
        if decision.search_requests:
            found_items: list[FoundCatalogItem] = []
            for search_request in decision.search_requests[:3]:
                found_items.extend(
                    await self._catalog_search.search_items(
                        query=search_request.query,
                        limit=search_request.limit,
                    )
                )
            return found_items
        if decision.search_query is None:
            return []
        return await self._catalog_search.search_items(
            query=decision.search_query,
            limit=_DEFAULT_SEARCH_LIMIT,
        )


def _should_update_brief(decision: RouterDecision) -> bool:
    if "update_brief" in decision.tool_intents:
        return True
    return decision.intent in {"brief_discovery", "mixed"}


def _action_plan_from_decision(decision: RouterDecision) -> ActionPlan:
    return ActionPlan(
        interface_mode=decision.interface_mode,
        workflow_stage=decision.workflow_stage,
        tool_intents=list(decision.tool_intents)
        if decision.tool_intents
        else _legacy_tool_intents(decision),
        search_requests=list(decision.search_requests),
        missing_fields=list(decision.missing_fields),
        clarification_questions=list(decision.clarification_questions),
    )


def _legacy_tool_intents(decision: RouterDecision) -> list[str]:
    if decision.should_search_now:
        return ["search_items"]
    if decision.intent in {"brief_discovery", "mixed"}:
        return ["update_brief"]
    return []


__all__ = ["ChatTurnUseCase"]
