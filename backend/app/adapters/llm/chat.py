from __future__ import annotations

from typing import Any

import httpx

from app.features.search.dto import ChatMessage


class ChatResponseError(RuntimeError):
    pass


class LMStudioChatClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._transport = transport

    async def complete(self, messages: list[ChatMessage]) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "temperature": 0,
            "stream": False,
        }
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.post(self._chat_completions_url(), json=payload)
            response.raise_for_status()
        return _content_from_response(response.json())

    def _chat_completions_url(self) -> str:
        if self._base_url.endswith("/chat/completions"):
            return self._base_url
        return f"{self._base_url}/chat/completions"


def _content_from_response(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ChatResponseError(
            "Unexpected LM Studio chat response shape",
        ) from exc
    return str(content).strip()


__all__ = ["ChatResponseError", "LMStudioChatClient"]
