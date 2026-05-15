from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.entrypoints.http.dependencies import get_chat_turn_uc
from app.entrypoints.http.schemas.assistant import (
    AssistantChatRequestIn,
    AssistantChatResponseOut,
)
from app.features.assistant.agent_graph import AssistantGraphRunner

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post(
    "/chat",
    response_model=AssistantChatResponseOut,
    operation_id="assistantChat",
    summary="Run one unified assistant chat turn",
    description=(
        "Routes a user message, merges the active brief state and calls catalog "
        "search when useful. The response keeps assistant prose, router state, "
        "brief state and found catalog rows as separate layers."
    ),
)
async def assistant_chat(
    request: AssistantChatRequestIn,
    uc: Annotated[AssistantGraphRunner, Depends(get_chat_turn_uc)],
) -> AssistantChatResponseOut:
    response = await uc.execute(request.to_domain())
    return AssistantChatResponseOut.from_domain(response)


__all__ = ["router"]
