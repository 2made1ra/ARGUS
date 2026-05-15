from __future__ import annotations

from typing import Any

import pytest
from app.adapters.llm.assistant_router import LMStudioAssistantRouterAdapter
from app.features.assistant.domain.llm_router.prompt import llm_router_json_schema
from app.features.assistant.dto import LLMRouterMessage, LLMStructuredRouterRequest


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class RecordingAsyncClient:
    calls: list[dict[str, Any]] = []
    timeouts: list[float] = []

    def __init__(self, *, timeout: float, transport: object | None = None) -> None:
        self.timeouts.append(timeout)
        self.transport = transport

    async def __aenter__(self) -> RecordingAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, *, json: dict[str, Any]) -> FakeResponse:
        self.calls.append({"url": url, "json": json})
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"intent":"supplier_search"}',
                        },
                    },
                ],
            },
        )


@pytest.fixture(autouse=True)
def clear_recording_client() -> None:
    RecordingAsyncClient.calls = []
    RecordingAsyncClient.timeouts = []


@pytest.mark.asyncio
async def test_assistant_router_uses_lm_studio_json_schema_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.adapters.llm.assistant_router.httpx.AsyncClient",
        RecordingAsyncClient,
    )
    adapter = LMStudioAssistantRouterAdapter(
        base_url="http://localhost:1234/v1/",
        model="local-model",
        timeout=12.0,
    )

    result = await adapter.route_structured(
        prompt=LLMStructuredRouterRequest(
            messages=[
                LLMRouterMessage(role="system", content="Return JSON."),
                LLMRouterMessage(role="user", content="найди инвентарь"),
            ],
        ),
    )

    assert result == '{"intent":"supplier_search"}'
    assert RecordingAsyncClient.timeouts == [12.0]
    assert RecordingAsyncClient.calls[0]["url"] == (
        "http://localhost:1234/v1/chat/completions"
    )
    payload = RecordingAsyncClient.calls[0]["json"]
    assert payload["model"] == "local-model"
    assert payload["messages"] == [
        {"role": "system", "content": "Return JSON."},
        {"role": "user", "content": "найди инвентарь"},
    ]
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["name"] == (
        "argus_assistant_router"
    )
    assert payload["response_format"]["json_schema"]["schema"]["type"] == "object"


def test_llm_router_schema_constrains_nested_brief_update_fields() -> None:
    schema = llm_router_json_schema()

    assert schema["required"] == ["interface_mode", "intent", "confidence"]
    brief_update = schema["properties"]["brief_update"]
    assert brief_update["additionalProperties"] is False
    assert set(brief_update["properties"]) >= {
        "event_type",
        "city",
        "budget_total",
        "service_needs",
    }
    service_needs = brief_update["properties"]["service_needs"]
    assert service_needs["items"]["required"] == ["category"]
    assert service_needs["items"]["additionalProperties"] is False
