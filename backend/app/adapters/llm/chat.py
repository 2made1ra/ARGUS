from __future__ import annotations

from typing import Any

import httpx
from langchain_openai import ChatOpenAI

from app.features.search.dto import ChatMessage


class ChatResponseError(RuntimeError):
    pass


class LMStudioChatClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
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
            response = await client.post(
                self._chat_completions_url(),
                json=payload,
                headers=_authorization_headers(self._api_key),
            )
            response.raise_for_status()
        return _content_from_response(response.json())

    def _chat_completions_url(self) -> str:
        if self._base_url.endswith("/chat/completions"):
            return self._base_url
        return f"{self._base_url}/chat/completions"


class LangChainChatClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "not-needed",
        timeout: float = 60.0,
    ) -> None:
        self._chat = ChatOpenAI(
            model=model,
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            timeout=timeout,
            temperature=0,
        )

    async def complete(self, messages: list[ChatMessage]) -> str:
        response = await self._chat.ainvoke(
            [(message.role, message.content) for message in messages],
        )
        content = getattr(response, "content", response)
        if isinstance(content, str):
            return content.strip()
        raise ChatResponseError("Unexpected LangChain chat response shape")


def _content_from_response(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ChatResponseError(
            "Unexpected LM Studio chat response shape",
        ) from exc
    return str(content).strip()


def _authorization_headers(api_key: str | None) -> dict[str, str] | None:
    if api_key is None or api_key == "":
        return None
    return {"Authorization": f"Bearer {api_key}"}


__all__ = ["ChatResponseError", "LangChainChatClient", "LMStudioChatClient"]
