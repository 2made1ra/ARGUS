from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypedDict, cast
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph

from app.features.assistant.brief import merge_brief
from app.features.assistant.dto import (
    ActionPlan,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantInterfaceMode,
    BriefState,
    CatalogItemDetail,
    CatalogSearchFilters,
    EventBriefWorkflowState,
    FoundCatalogItem,
    RenderedBriefSection,
    RenderedEventBrief,
    RouterDecision,
    SearchRequest,
    SupplierVerificationResult,
    ToolIntent,
)
from app.features.assistant.ports import (
    CatalogItemDetailsTool,
    CatalogSearchTool,
    EventBriefRenderTool,
    SupplierVerificationTool,
)

_ALLOWED_TOOL_NAMES: set[str] = {
    "update_brief",
    "search_items",
    "get_item_details",
    "select_item",
    "compare_items",
    "verify_supplier_status",
    "render_event_brief",
}


@dataclass(frozen=True, slots=True)
class ProposedToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AssistantAgentPlan:
    message: str | None = None
    interface_mode: AssistantInterfaceMode = AssistantInterfaceMode.CHAT_SEARCH
    workflow_stage: EventBriefWorkflowState = (
        EventBriefWorkflowState.SEARCH_CLARIFYING
    )
    brief_update: BriefState = field(default_factory=BriefState)
    tool_calls: list[ProposedToolCall] = field(default_factory=list)
    clarification_questions: list[str] = field(default_factory=list)
    confidence: float = 0.8
    intent: str = "clarification"


class AssistantAgentPlanner(Protocol):
    async def plan(self, state: dict[str, Any]) -> AssistantAgentPlan: ...


class DemoAssistantAgentPlanner:
    async def plan(self, state: dict[str, Any]) -> AssistantAgentPlan:
        request = cast(AssistantChatRequest, state["request"])
        message = request.message.strip()
        if not message:
            return AssistantAgentPlan(message="Уточните параметры задачи.")
        return AssistantAgentPlan(
            message="Демо-режим assistant работает без LLM planner.",
            intent="clarification",
        )


class AssistantGraphState(TypedDict, total=False):
    request: AssistantChatRequest
    session_id: UUID
    brief: BriefState
    brief_update: BriefState
    plan: AssistantAgentPlan
    action_plan: ActionPlan
    found_items: list[FoundCatalogItem]
    item_details: list[CatalogItemDetail]
    verification_results: list[SupplierVerificationResult]
    rendered_brief: RenderedEventBrief | None
    validated_tool_calls: list[ProposedToolCall]
    skipped_actions: list[str]
    iterations: int
    backend_tool_calls_used: int
    response: AssistantChatResponse


class AssistantGraphRunner:
    def __init__(
        self,
        *,
        planner: AssistantAgentPlanner,
        catalog_search: CatalogSearchTool | None = None,
        item_details: CatalogItemDetailsTool | None = None,
        supplier_verification: SupplierVerificationTool | None = None,
        brief_renderer: EventBriefRenderTool | None = None,
        max_tool_calls_per_turn: int = 3,
        max_iterations: int = 4,
    ) -> None:
        self._planner = planner
        self._catalog_search = catalog_search
        self._item_details = item_details
        self._supplier_verification = supplier_verification
        self._brief_renderer = brief_renderer or GraphEventBriefRenderer()
        self._max_tool_calls_per_turn = max(0, max_tool_calls_per_turn)
        self._max_iterations = max(1, max_iterations)
        self._graph = self._build_graph()

    async def execute(self, request: AssistantChatRequest) -> AssistantChatResponse:
        state: AssistantGraphState = {"request": request}
        result = await self._graph.ainvoke(state)
        return cast(AssistantChatResponse, result["response"])

    def _build_graph(self) -> Any:
        graph = StateGraph(AssistantGraphState)
        graph.add_node("prepare_input", self._prepare_input)
        graph.add_node("agent_plan", self._agent_plan)
        graph.add_node("validate_tool_calls", self._validate_tool_calls)
        graph.add_node("execute_tools", self._execute_tools)
        graph.add_node("compose_response", self._compose_response)
        graph.add_edge(START, "prepare_input")
        graph.add_edge("prepare_input", "agent_plan")
        graph.add_edge("agent_plan", "validate_tool_calls")
        graph.add_conditional_edges(
            "validate_tool_calls",
            self._next_after_validation,
            {
                "execute_tools": "execute_tools",
                "compose_response": "compose_response",
            },
        )
        graph.add_edge("execute_tools", "agent_plan")
        graph.add_edge("compose_response", END)
        return graph.compile()

    async def _prepare_input(self, state: AssistantGraphState) -> AssistantGraphState:
        request = state["request"]
        return {
            "session_id": request.session_id or uuid4(),
            "brief": request.brief if request.brief is not None else BriefState(),
            "brief_update": BriefState(),
            "found_items": [],
            "item_details": [],
            "verification_results": [],
            "rendered_brief": None,
            "validated_tool_calls": [],
            "skipped_actions": [],
            "iterations": 0,
            "backend_tool_calls_used": 0,
            "action_plan": ActionPlan(
                interface_mode=AssistantInterfaceMode.CHAT_SEARCH,
                workflow_stage=EventBriefWorkflowState.SEARCH_CLARIFYING,
            ),
        }

    async def _agent_plan(self, state: AssistantGraphState) -> AssistantGraphState:
        planner_state = dict(state)
        plan = await self._planner.plan(planner_state)
        return {
            "plan": plan,
            "brief_update": plan.brief_update,
            "iterations": state.get("iterations", 0) + 1,
        }

    async def _validate_tool_calls(
        self,
        state: AssistantGraphState,
    ) -> AssistantGraphState:
        plan = state["plan"]
        current_action = state["action_plan"]
        skipped_actions = list(state.get("skipped_actions", []))
        validated: list[ProposedToolCall] = []
        search_requests = list(current_action.search_requests)
        tool_intents = list(current_action.tool_intents)
        verification_targets = list(current_action.verification_targets)
        comparison_targets = list(current_action.comparison_targets)
        item_detail_ids = list(current_action.item_detail_ids)
        render_requested = current_action.render_requested
        backend_tool_calls_used = state.get("backend_tool_calls_used", 0)
        remaining_budget = self._max_tool_calls_per_turn - backend_tool_calls_used
        allowed_candidate_ids = _allowed_candidate_item_ids(
            request=state["request"],
            brief=state["brief"],
        )

        for call in plan.tool_calls:
            if call.name not in _ALLOWED_TOOL_NAMES:
                skipped_actions.append(f"unsupported_tool:{call.name}")
                continue
            if _tool_uses_backend_call(call.name) and remaining_budget <= 0:
                skipped_actions.append(f"tool_call_limit_reached:{call.name}")
                continue
            if call.name == "search_items":
                request = _search_request_from_args(call.args)
                if request is None:
                    skipped_actions.append("invalid_tool_args:search_items")
                    continue
                search_requests.append(request)
                if "search_items" not in tool_intents:
                    tool_intents.append("search_items")
                validated.append(call)
                remaining_budget -= 1
                backend_tool_calls_used += 1
                continue
            if call.name == "update_brief":
                if "update_brief" not in tool_intents:
                    tool_intents.append("update_brief")
                validated.append(call)
                continue
            if call.name == "get_item_details":
                ids = _authorized_item_ids(
                    _item_ids_from_args(call.args),
                    allowed_candidate_ids,
                )
                if not ids:
                    skipped_actions.append("invalid_tool_args:get_item_details")
                    continue
                item_detail_ids.extend(ids)
                if "get_item_details" not in tool_intents:
                    tool_intents.append("get_item_details")
                validated.append(call)
                remaining_budget -= 1
                backend_tool_calls_used += 1
                continue
            if call.name == "select_item":
                ids = _authorized_item_ids(
                    _item_ids_from_args(call.args),
                    allowed_candidate_ids,
                )
                if not ids:
                    skipped_actions.append("invalid_tool_args:select_item")
                    continue
                if "select_item" not in tool_intents:
                    tool_intents.append("select_item")
                validated.append(call)
                continue
            if call.name == "compare_items":
                ids = _authorized_item_ids(
                    _item_ids_from_args(call.args),
                    allowed_candidate_ids,
                )
                if not ids:
                    skipped_actions.append("invalid_tool_args:compare_items")
                    continue
                comparison_targets.extend(ids)
                if "compare_items" not in tool_intents:
                    tool_intents.append("compare_items")
                validated.append(call)
                remaining_budget -= 1
                backend_tool_calls_used += 1
                continue
            if call.name == "verify_supplier_status":
                ids = _verification_target_ids(
                    call.args,
                    request=state["request"],
                    brief=state["brief"],
                )
                ids = _authorized_item_ids(ids, allowed_candidate_ids)
                if not ids:
                    skipped_actions.append("verification_targets_missing")
                    continue
                verification_targets.extend(ids)
                if "verify_supplier_status" not in tool_intents:
                    tool_intents.append("verify_supplier_status")
                validated.append(call)
                remaining_budget -= 1
                backend_tool_calls_used += 1
                continue
            if call.name == "render_event_brief":
                render_requested = True
                if "render_event_brief" not in tool_intents:
                    tool_intents.append("render_event_brief")
                validated.append(call)
                remaining_budget -= 1
                backend_tool_calls_used += 1
                continue

        return {
            "validated_tool_calls": validated,
            "skipped_actions": skipped_actions,
            "backend_tool_calls_used": backend_tool_calls_used,
            "action_plan": ActionPlan(
                interface_mode=plan.interface_mode,
                workflow_stage=plan.workflow_stage,
                tool_intents=cast(list[ToolIntent], tool_intents),
                search_requests=search_requests,
                verification_targets=_dedupe_uuid(verification_targets),
                comparison_targets=_dedupe_uuid(comparison_targets),
                item_detail_ids=_dedupe_uuid(item_detail_ids),
                render_requested=render_requested,
                clarification_questions=list(plan.clarification_questions),
                skipped_actions=skipped_actions,
            ),
        }

    async def _execute_tools(self, state: AssistantGraphState) -> AssistantGraphState:
        action_plan = state["action_plan"]
        skipped_actions = list(state.get("skipped_actions", []))
        found_items = list(state.get("found_items", []))
        item_details = list(state.get("item_details", []))
        verification_results = list(state.get("verification_results", []))
        rendered_brief = state.get("rendered_brief")
        brief = merge_brief(state["brief"], state.get("brief_update", BriefState()))

        for call in state.get("validated_tool_calls", []):
            if call.name == "search_items":
                request = _search_request_from_args(call.args)
                if request is None:
                    continue
                if self._catalog_search is None:
                    skipped_actions.append("search_items_unavailable")
                    continue
                results = await self._catalog_search.search_items(
                    query=request.query,
                    limit=request.limit,
                    filters=request.filters,
                )
                found_items.extend(results)
                continue
            if call.name == "get_item_details":
                item_details.extend(
                    await self._load_item_details(
                        _authorized_item_ids(
                            _item_ids_from_args(call.args),
                            _allowed_candidate_item_ids(
                                request=state["request"],
                                brief=brief,
                            ),
                        ),
                        skipped_actions,
                    ),
                )
                continue
            if call.name == "select_item":
                brief = merge_brief(
                    brief,
                    BriefState(
                        selected_item_ids=_authorized_item_ids(
                            _item_ids_from_args(call.args),
                            _allowed_candidate_item_ids(
                                request=state["request"],
                                brief=brief,
                            ),
                        ),
                    ),
                )
                continue
            if call.name == "compare_items":
                item_details.extend(
                    await self._load_item_details(
                        _authorized_item_ids(
                            _item_ids_from_args(call.args),
                            _allowed_candidate_item_ids(
                                request=state["request"],
                                brief=brief,
                            ),
                        ),
                        skipped_actions,
                    ),
                )
                continue
            if call.name == "verify_supplier_status":
                targets = _verification_target_ids(
                    call.args,
                    request=state["request"],
                    brief=brief,
                )
                targets = _authorized_item_ids(
                    targets,
                    _allowed_candidate_item_ids(
                        request=state["request"],
                        brief=brief,
                    ),
                )
                verification_results.extend(
                    await self._verify_suppliers(targets, skipped_actions),
                )
                continue
            if call.name == "render_event_brief":
                selected_details = [
                    detail
                    for detail in item_details
                    if detail.id in set(brief.selected_item_ids)
                ]
                if not selected_details and brief.selected_item_ids:
                    selected_details = await self._load_item_details(
                        brief.selected_item_ids,
                        skipped_actions,
                    )
                    item_details.extend(selected_details)
                rendered_brief = self._brief_renderer.render(
                    brief=brief,
                    selected_items=selected_details,
                    verification_results=verification_results,
                    found_items=found_items,
                )

        return {
            "brief": brief,
            "found_items": found_items,
            "item_details": _dedupe_details(item_details),
            "verification_results": verification_results,
            "rendered_brief": rendered_brief,
            "skipped_actions": skipped_actions,
            "validated_tool_calls": [],
            "action_plan": _replace_skipped(action_plan, skipped_actions),
        }

    def _next_after_validation(self, state: AssistantGraphState) -> str:
        if state.get("validated_tool_calls") and (
            state.get("iterations", 0) < self._max_iterations
        ):
            return "execute_tools"
        return "compose_response"

    async def _compose_response(
        self,
        state: AssistantGraphState,
    ) -> AssistantGraphState:
        action_plan = _replace_skipped(
            state["action_plan"],
            state.get("skipped_actions", []),
        )
        plan = state.get("plan", AssistantAgentPlan())
        found_items = state.get("found_items", [])
        brief = state["brief"]
        router = RouterDecision(
            intent=cast(Any, plan.intent),
            confidence=plan.confidence,
            known_facts={},
            missing_fields=[],
            should_search_now="search_items" in action_plan.tool_intents,
            search_query=(
                action_plan.search_requests[0].query
                if action_plan.search_requests
                else None
            ),
            brief_update=state.get("brief_update", BriefState()),
            interface_mode=action_plan.interface_mode,
            workflow_stage=action_plan.workflow_stage,
            search_requests=list(action_plan.search_requests),
            tool_intents=list(action_plan.tool_intents),
            clarification_questions=list(action_plan.clarification_questions),
            user_visible_summary=plan.message,
            action_plan=action_plan,
        )
        response = AssistantChatResponse(
            session_id=state["session_id"],
            message=plan.message or _default_message(action_plan, found_items),
            router=router,
            brief=brief,
            found_items=found_items,
            item_details=state.get("item_details", []),
            ui_mode=action_plan.interface_mode,
            action_plan=action_plan,
            verification_results=state.get("verification_results", []),
            rendered_brief=state.get("rendered_brief"),
        )
        return {"response": response}

    async def _load_item_details(
        self,
        item_ids: list[UUID],
        skipped_actions: list[str],
    ) -> list[CatalogItemDetail]:
        if self._item_details is None:
            skipped_actions.append("item_details_unavailable")
            return []
        details: list[CatalogItemDetail] = []
        for item_id in _dedupe_uuid(item_ids):
            detail = await self._item_details.get_item_details(item_id=item_id)
            if detail is None:
                skipped_actions.append(f"item_detail_not_found:{item_id}")
                continue
            details.append(detail)
        return details

    async def _verify_suppliers(
        self,
        item_ids: list[UUID],
        skipped_actions: list[str],
    ) -> list[SupplierVerificationResult]:
        if self._supplier_verification is None:
            skipped_actions.append("supplier_verification_unavailable")
            return []
        details = await self._load_item_details(item_ids, skipped_actions)
        results: list[SupplierVerificationResult] = []
        verified_by_inn: dict[str, SupplierVerificationResult] = {}
        for detail in details:
            if not detail.supplier_inn:
                results.append(
                    SupplierVerificationResult(
                        item_id=detail.id,
                        supplier_name=detail.supplier,
                        supplier_inn=None,
                        ogrn=None,
                        legal_name=None,
                        status="not_verified",
                        source="catalog",
                        checked_at=None,
                        risk_flags=["supplier_inn_missing"],
                        message="У поставщика в каталоге нет ИНН.",
                    ),
                )
                continue
            result = verified_by_inn.get(detail.supplier_inn)
            if result is None:
                result = await self._supplier_verification.verify_by_inn_or_ogrn(
                    inn=detail.supplier_inn,
                    ogrn=None,
                    supplier_name=detail.supplier,
                )
                verified_by_inn[detail.supplier_inn] = result
            results.append(
                SupplierVerificationResult(
                    item_id=detail.id,
                    supplier_name=result.supplier_name,
                    supplier_inn=result.supplier_inn,
                    ogrn=result.ogrn,
                    legal_name=result.legal_name,
                    status=result.status,
                    source=result.source,
                    checked_at=result.checked_at,
                    risk_flags=list(result.risk_flags),
                    message=result.message,
                ),
            )
        return results


def _search_request_from_args(args: dict[str, Any]) -> SearchRequest | None:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return None
    limit = args.get("limit", 8)
    if not isinstance(limit, int) or limit < 1:
        return None
    service_category = args.get("service_category")
    if service_category is not None and not isinstance(service_category, str):
        return None
    return SearchRequest(
        query=query.strip(),
        service_category=service_category,
        limit=limit,
        filters=_catalog_filters_from_args(args),
    )


def _catalog_filters_from_args(args: dict[str, Any]) -> CatalogSearchFilters:
    filters = args.get("filters")
    payload = filters if isinstance(filters, dict) else args
    return CatalogSearchFilters(
        supplier_city_normalized=_optional_str(payload.get("supplier_city_normalized")),
        category=_optional_str(payload.get("category")),
        service_category=_optional_str(
            payload.get("service_category") or args.get("service_category"),
        ),
        supplier_status_normalized=_optional_str(
            payload.get("supplier_status_normalized"),
        ),
        has_vat=_optional_str(payload.get("has_vat")),
        vat_mode=_optional_str(payload.get("vat_mode")),
        unit_price_min=_optional_int(payload.get("unit_price_min")),
        unit_price_max=_optional_int(payload.get("unit_price_max")),
    )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _item_ids_from_args(args: dict[str, Any]) -> list[UUID]:
    values: list[Any] = []
    if "item_id" in args:
        values.append(args["item_id"])
    item_ids = args.get("item_ids")
    if isinstance(item_ids, list):
        values.extend(item_ids)

    parsed: list[UUID] = []
    for value in values:
        if isinstance(value, UUID):
            parsed.append(value)
            continue
        if isinstance(value, str):
            try:
                parsed.append(UUID(value))
            except ValueError:
                continue
    return _dedupe_uuid(parsed)


def _verification_target_ids(
    args: dict[str, Any],
    *,
    request: AssistantChatRequest,
    brief: BriefState,
) -> list[UUID]:
    explicit = _item_ids_from_args(args)
    if explicit:
        return explicit
    if brief.selected_item_ids:
        return _dedupe_uuid(brief.selected_item_ids)
    if request.candidate_item_ids:
        return _dedupe_uuid(request.candidate_item_ids)
    return _dedupe_uuid([candidate.item_id for candidate in request.visible_candidates])


def _allowed_candidate_item_ids(
    *,
    request: AssistantChatRequest,
    brief: BriefState,
) -> set[UUID]:
    return {
        *brief.selected_item_ids,
        *request.candidate_item_ids,
        *(candidate.item_id for candidate in request.visible_candidates),
    }


def _authorized_item_ids(values: list[UUID], allowed: set[UUID]) -> list[UUID]:
    if not values:
        return []
    return [item_id for item_id in _dedupe_uuid(values) if item_id in allowed]


def _dedupe_uuid(values: list[UUID]) -> list[UUID]:
    seen: set[UUID] = set()
    result: list[UUID] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_details(values: list[CatalogItemDetail]) -> list[CatalogItemDetail]:
    seen: set[UUID] = set()
    result: list[CatalogItemDetail] = []
    for value in values:
        if value.id in seen:
            continue
        seen.add(value.id)
        result.append(value)
    return result


def _tool_uses_backend_call(name: str) -> bool:
    return name in {
        "search_items",
        "get_item_details",
        "compare_items",
        "verify_supplier_status",
        "render_event_brief",
    }


def _replace_skipped(action_plan: ActionPlan, skipped: list[str]) -> ActionPlan:
    return ActionPlan(
        interface_mode=action_plan.interface_mode,
        workflow_stage=action_plan.workflow_stage,
        tool_intents=list(action_plan.tool_intents),
        search_requests=list(action_plan.search_requests),
        verification_targets=list(action_plan.verification_targets),
        comparison_targets=list(action_plan.comparison_targets),
        item_detail_ids=list(action_plan.item_detail_ids),
        render_requested=action_plan.render_requested,
        missing_fields=list(action_plan.missing_fields),
        clarification_questions=list(action_plan.clarification_questions),
        skipped_actions=list(skipped),
    )


def _default_message(
    action_plan: ActionPlan,
    found_items: list[FoundCatalogItem],
) -> str:
    if "search_items" in action_plan.tool_intents and found_items:
        return (
            "Нашел кандидатов в каталоге. Карточки ниже - предварительная "
            "выдача по вашему запросу."
        )
    if "search_items" in action_plan.tool_intents:
        return (
            "В каталоге нет строк по этому запросу. Уточните услугу, категорию, "
            "город, поставщика или ИНН, и я попробую сузить поиск."
        )
    return "Уточните параметры задачи."


class GraphEventBriefRenderer:
    def render(
        self,
        *,
        brief: BriefState,
        selected_items: list[CatalogItemDetail],
        verification_results: list[SupplierVerificationResult],
        found_items: list[FoundCatalogItem] | None = None,
    ) -> RenderedEventBrief:
        candidates = found_items if found_items is not None else []
        open_questions = list(brief.open_questions)
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
            _section("Блоки услуг", _service_lines(brief)),
            _section(
                "Выбранные позиции",
                _selected_item_lines(
                    brief=brief,
                    selected_items=selected_items,
                    found_items=candidates,
                ),
            ),
            _section(
                "Проверка подрядчиков",
                _verification_lines(verification_results),
            ),
            _section("Открытые вопросы", open_questions if open_questions else ["Нет"]),
        ]
        return RenderedEventBrief(
            title="Бриф мероприятия",
            sections=sections,
            open_questions=open_questions,
            evidence={
                "selected_item_ids": [
                    str(item_id) for item_id in brief.selected_item_ids
                ],
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
    lines.extend(f"{need.category}: {need.priority}" for need in brief.service_needs)
    return lines


def _selected_item_lines(
    *,
    brief: BriefState,
    selected_items: list[CatalogItemDetail],
    found_items: list[FoundCatalogItem],
) -> list[str]:
    detail_lines = [
        f"{item.name}; поставщик: {item.supplier or 'не указан'}; "
        f"цена: {item.unit_price:.2f}/{item.unit}"
        for item in selected_items
    ]
    if detail_lines:
        return detail_lines
    selected_ids = set(brief.selected_item_ids)
    found_lines = [
        f"{item.name}; поставщик: {item.supplier or 'не указан'}; "
        f"цена: {item.unit_price:.2f}/{item.unit}"
        for item in found_items
        if item.id in selected_ids
    ]
    if found_lines:
        return found_lines
    if selected_ids:
        return [", ".join(str(item_id) for item_id in brief.selected_item_ids)]
    return ["Позиции пока не выбраны"]


def _verification_lines(
    results: list[SupplierVerificationResult],
) -> list[str]:
    if not results:
        return ["Проверка подрядчиков еще не выполнялась"]
    return [
        "; ".join(
            part
            for part in (
                result.supplier_name,
                f"ИНН: {result.supplier_inn}" if result.supplier_inn else None,
                f"статус: {result.status}",
                f"источник: {result.source}",
            )
            if part is not None
        )
        for result in results
    ]


__all__ = [
    "AssistantAgentPlan",
    "AssistantAgentPlanner",
    "AssistantGraphRunner",
    "DemoAssistantAgentPlanner",
    "GraphEventBriefRenderer",
    "ProposedToolCall",
]
