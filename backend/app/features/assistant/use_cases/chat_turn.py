from __future__ import annotations

from uuid import uuid4

from app.features.assistant.domain.response_composer import ResponseComposer
from app.features.assistant.domain.tool_executor import ToolExecutor
from app.features.assistant.dto import (
    ActionPlan,
    AssistantChatRequest,
    AssistantChatResponse,
    BriefState,
    RouterDecision,
    SearchRequest,
)
from app.features.assistant.ports import AssistantRouter, CatalogSearchTool

_DEFAULT_SEARCH_LIMIT = 10


class ChatTurnUseCase:
    def __init__(
        self,
        *,
        router: AssistantRouter,
        catalog_search: CatalogSearchTool | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self._router = router
        self._tool_executor = (
            tool_executor
            if tool_executor is not None
            else ToolExecutor(catalog_search=catalog_search, item_details=None)
        )

    async def execute(self, request: AssistantChatRequest) -> AssistantChatResponse:
        current_brief = request.brief if request.brief is not None else BriefState()
        decision = await self._router.route(
            message=request.message,
            brief=current_brief,
            recent_turns=list(request.recent_turns),
            visible_candidates=list(request.visible_candidates),
        )
        action_plan = (
            decision.action_plan
            if decision.action_plan is not None
            else _action_plan_from_decision(decision)
        )
        tool_results = await self._tool_executor.execute(
            action_plan=action_plan,
            brief=current_brief,
            brief_update=decision.brief_update,
            message=request.message,
            recent_turns=list(request.recent_turns),
            visible_candidates=list(request.visible_candidates),
            candidate_item_ids=list(request.candidate_item_ids),
        )
        return AssistantChatResponse(
            session_id=request.session_id or uuid4(),
            message=ResponseComposer().compose_from_decision(
                decision=decision,
                brief=tool_results.brief,
                found_items=tool_results.found_items,
            ),
            router=decision,
            brief=tool_results.brief,
            found_items=tool_results.found_items,
            ui_mode=decision.interface_mode,
            action_plan=action_plan,
            verification_results=tool_results.verification_results,
            rendered_brief=tool_results.rendered_brief,
        )


def _should_update_brief(decision: RouterDecision) -> bool:
    if "update_brief" in decision.tool_intents:
        return True
    return decision.intent in {"brief_discovery", "mixed"}


def _action_plan_from_decision(decision: RouterDecision) -> ActionPlan:
    search_requests = list(decision.search_requests)
    if not search_requests and decision.search_query is not None:
        search_requests = [
            SearchRequest(
                query=decision.search_query,
                limit=_DEFAULT_SEARCH_LIMIT,
            ),
        ]
    return ActionPlan(
        interface_mode=decision.interface_mode,
        workflow_stage=decision.workflow_stage,
        tool_intents=list(decision.tool_intents)
        if decision.tool_intents
        else _legacy_tool_intents(decision),
        search_requests=search_requests,
        missing_fields=list(decision.missing_fields),
        clarification_questions=list(decision.clarification_questions),
    )


def _legacy_tool_intents(decision: RouterDecision) -> list[str]:
    intents: list[str] = []
    if decision.intent in {"brief_discovery", "mixed"}:
        intents.append("update_brief")
    if decision.should_search_now:
        intents.append("search_items")
    return intents


__all__ = ["ChatTurnUseCase"]
