from __future__ import annotations

from dataclasses import fields
from typing import Any, Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field

from app.features.assistant.agent_graph import (
    AssistantAgentPlan,
    ProposedToolCall,
)
from app.features.assistant.dto import (
    AssistantChatRequest,
    AssistantInterfaceMode,
    BriefState,
    EventBriefWorkflowState,
)


class ToolCallOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class AssistantAgentPlanOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str | None = None
    interface_mode: Literal["brief_workspace", "chat_search"] = "chat_search"
    workflow_stage: Literal[
        "intake",
        "clarifying",
        "service_planning",
        "supplier_searching",
        "supplier_verification",
        "brief_ready",
        "brief_rendered",
        "search_clarifying",
        "searching",
        "search_results_shown",
    ] = "search_clarifying"
    intent: str = "clarification"
    confidence: float = 0.8
    brief_update: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[ToolCallOutput] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)


class LangChainAssistantAgentPlanner:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float = 30.0,
        api_key: str = "not-needed",
    ) -> None:
        self._chat = ChatOpenAI(
            model=model,
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            timeout=timeout,
            temperature=0,
        )

    async def plan(self, state: dict[str, Any]) -> AssistantAgentPlan:
        structured = self._chat.with_structured_output(
            AssistantAgentPlanOutput,
            method="json_schema",
            strict=True,
        )
        output = await structured.ainvoke(_messages_from_state(state))
        if isinstance(output, dict):
            output = AssistantAgentPlanOutput.model_validate(output)
        if not isinstance(output, AssistantAgentPlanOutput):
            output = AssistantAgentPlanOutput.model_validate(output)
        return AssistantAgentPlan(
            message=output.message,
            interface_mode=AssistantInterfaceMode(output.interface_mode),
            workflow_stage=EventBriefWorkflowState(output.workflow_stage),
            brief_update=_brief_update_from_payload(output.brief_update),
            tool_calls=[
                ProposedToolCall(name=tool.name, args=dict(tool.args))
                for tool in output.tool_calls
            ],
            clarification_questions=list(output.clarification_questions),
            confidence=output.confidence,
            intent=output.intent,
        )


def _messages_from_state(state: dict[str, Any]) -> list[tuple[str, str]]:
    request = state["request"]
    if not isinstance(request, AssistantChatRequest):
        raise TypeError("assistant graph state does not contain AssistantChatRequest")
    brief = state.get("brief") or request.brief or BriefState()
    found_items = state.get("found_items", [])
    system = (
        "You are ARGUS LangGraph assistant planner. Return structured JSON only. "
        "You may propose tool_calls, but backend validates and executes them. "
        "Do not invent catalog prices, supplier facts, legal statuses, SQL or "
        "HTTP calls. "
        "Allowed tool names: update_brief, search_items, get_item_details, "
        "select_item, "
        "compare_items, verify_supplier_status, render_event_brief."
    )
    user = (
        f"User message: {request.message}\n"
        f"Current brief: {brief!r}\n"
        f"Recent turns: {request.recent_turns!r}\n"
        f"Visible candidates: {request.visible_candidates!r}\n"
        f"Candidate item ids: {request.candidate_item_ids!r}\n"
        f"Found items from previous graph step: {found_items!r}"
    )
    return [("system", system), ("user", user)]


def _brief_update_from_payload(payload: dict[str, Any]) -> BriefState:
    allowed = {field.name for field in fields(BriefState)}
    values = {key: value for key, value in payload.items() if key in allowed}
    return BriefState(**values)


__all__ = [
    "AssistantAgentPlanOutput",
    "LangChainAssistantAgentPlanner",
    "ToolCallOutput",
]
