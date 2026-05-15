from __future__ import annotations

from typing import Any

import pytest
from app.adapters.llm.chat import LangChainChatClient, LMStudioChatClient
from app.features.search.dto import ChatMessage


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class RecordingAsyncClient:
    calls: list[dict[str, Any]] = []

    def __init__(self, *, timeout: float, transport: object | None = None) -> None:
        self.timeout = timeout
        self.transport = transport

    async def __aenter__(self) -> RecordingAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "headers": headers})
        return FakeResponse({"choices": [{"message": {"content": "Готово"}}]})


@pytest.fixture(autouse=True)
def clear_recording_client() -> None:
    RecordingAsyncClient.calls = []


@pytest.mark.asyncio
async def test_chat_client_sends_bearer_token_when_api_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.adapters.llm.chat.httpx.AsyncClient",
        RecordingAsyncClient,
    )
    client = LMStudioChatClient(
        base_url="https://api.vsellm.ru/v1",
        model="openai/gpt-oss-120b",
        api_key="secret-token",
    )

    result = await client.complete([ChatMessage(role="user", content="Привет!")])

    assert result == "Готово"
    assert RecordingAsyncClient.calls[0]["headers"] == {
        "Authorization": "Bearer secret-token",
    }


class FakeAIMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeChatOpenAI:
    calls: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    async def ainvoke(self, messages: list[tuple[str, str]]) -> FakeAIMessage:
        self.calls.append({"kwargs": self.kwargs, "messages": messages})
        return FakeAIMessage("Ответ LangChain")


@pytest.mark.asyncio
async def test_langchain_chat_client_uses_openai_compatible_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeChatOpenAI.calls = []
    monkeypatch.setattr("app.adapters.llm.chat.ChatOpenAI", FakeChatOpenAI)
    client = LangChainChatClient(
        base_url="https://api.vsellm.ru/v1",
        model="openai/gpt-oss-120b",
        api_key="secret-token",
        timeout=12.5,
    )

    result = await client.complete([ChatMessage(role="user", content="Привет!")])

    assert result == "Ответ LangChain"
    assert FakeChatOpenAI.calls == [
        {
            "kwargs": {
                "model": "openai/gpt-oss-120b",
                "base_url": "https://api.vsellm.ru/v1",
                "api_key": "secret-token",
                "timeout": 12.5,
                "temperature": 0,
            },
            "messages": [("user", "Привет!")],
        },
    ]
