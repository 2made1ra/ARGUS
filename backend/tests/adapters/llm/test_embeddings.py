from typing import Any

import httpx
import pytest
from app.adapters.llm.embeddings import (
    EmbeddingDimensionMismatch,
    EmbeddingResponseError,
    LMStudioEmbeddings,
)


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
    trust_envs: list[bool | None] = []

    def __init__(self, *, timeout: float, trust_env: bool | None = None) -> None:
        self.timeouts.append(timeout)
        self.trust_envs.append(trust_env)

    async def __aenter__(self) -> "RecordingAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, *, json: dict[str, Any]) -> FakeResponse:
        self.calls.append({"url": url, "json": json})
        embeddings = [
            {"embedding": _embedding_for_text(text)}
            for text in json["input"]
        ]
        return FakeResponse({"data": embeddings})


class MismatchedDimensionAsyncClient:
    def __init__(self, *, timeout: float, trust_env: bool | None = None) -> None:
        self.timeout = timeout
        self.trust_env = trust_env

    async def __aenter__(self) -> "MismatchedDimensionAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, *, json: dict[str, Any]) -> FakeResponse:
        return FakeResponse({"data": [{"embedding": [0.0] * 384}]})


class MissingDataAsyncClient:
    def __init__(self, *, timeout: float, trust_env: bool | None = None) -> None:
        self.timeout = timeout
        self.trust_env = trust_env

    async def __aenter__(self) -> "MissingDataAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, *, json: dict[str, Any]) -> FakeResponse:
        return FakeResponse({"error": "Unexpected endpoint or method"})


class FailingAsyncClient:
    def __init__(self, *, timeout: float, trust_env: bool | None = None) -> None:
        self.timeout = timeout
        self.trust_env = trust_env

    async def __aenter__(self) -> "FailingAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, *, json: dict[str, Any]) -> FakeResponse:
        raise httpx.ConnectError("connection refused")


def _embedding_for_text(text: str) -> list[float]:
    index = int(text.removeprefix("text-"))
    return [float(index), float(index + 1), float(index + 2)]


@pytest.fixture(autouse=True)
def clear_recording_client() -> None:
    RecordingAsyncClient.calls = []
    RecordingAsyncClient.timeouts = []
    RecordingAsyncClient.trust_envs = []


@pytest.mark.asyncio
async def test_embed_batches_texts_by_32_and_preserves_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.adapters.llm.embeddings.httpx.AsyncClient",
        RecordingAsyncClient,
    )
    texts = [f"text-{index}" for index in range(100)]
    embeddings = LMStudioEmbeddings(
        base_url="http://localhost:1234/v1/",
        model="nomic-embed-text-v1.5",
        batch_size=32,
        timeout=12.0,
        embedding_dim=3,
    )

    result = await embeddings.embed(texts)

    assert [len(call["json"]["input"]) for call in RecordingAsyncClient.calls] == [
        32,
        32,
        32,
        4,
    ]
    assert {call["url"] for call in RecordingAsyncClient.calls} == {
        "http://localhost:1234/v1/embeddings",
    }
    assert {call["json"]["model"] for call in RecordingAsyncClient.calls} == {
        "nomic-embed-text-v1.5",
    }
    assert RecordingAsyncClient.calls[0]["json"]["input"] == texts[:32]
    assert RecordingAsyncClient.calls[-1]["json"]["input"] == texts[96:]
    assert RecordingAsyncClient.timeouts == [12.0]
    assert result == [_embedding_for_text(text) for text in texts]


@pytest.mark.asyncio
async def test_embed_disables_environment_proxy_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.adapters.llm.embeddings.httpx.AsyncClient",
        RecordingAsyncClient,
    )
    embeddings = LMStudioEmbeddings(
        base_url="http://192.168.0.65:1234/v1",
        embedding_dim=3,
    )

    await embeddings.embed(["text-1"])

    assert RecordingAsyncClient.trust_envs == [False]


@pytest.mark.asyncio
async def test_embed_raises_for_embedding_dimension_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.adapters.llm.embeddings.httpx.AsyncClient",
        MismatchedDimensionAsyncClient,
    )
    embeddings = LMStudioEmbeddings(
        base_url="http://localhost:1234/v1",
        embedding_dim=768,
    )

    with pytest.raises(EmbeddingDimensionMismatch) as exc_info:
        await embeddings.embed(["text"])

    assert exc_info.value.actual == 384
    assert exc_info.value.expected == 768


@pytest.mark.asyncio
async def test_embed_raises_for_unexpected_response_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.adapters.llm.embeddings.httpx.AsyncClient",
        MissingDataAsyncClient,
    )
    embeddings = LMStudioEmbeddings(base_url="http://localhost:1234")

    with pytest.raises(EmbeddingResponseError):
        await embeddings.embed(["text"])


@pytest.mark.asyncio
async def test_embed_propagates_network_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.adapters.llm.embeddings.httpx.AsyncClient",
        FailingAsyncClient,
    )
    embeddings = LMStudioEmbeddings(base_url="http://localhost:1234/v1")

    with pytest.raises(httpx.ConnectError):
        await embeddings.embed(["text"])


@pytest.mark.asyncio
async def test_embed_returns_empty_list_without_http_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.adapters.llm.embeddings.httpx.AsyncClient",
        RecordingAsyncClient,
    )
    embeddings = LMStudioEmbeddings(base_url="http://localhost:1234/v1")

    result = await embeddings.embed([])

    assert result == []
    assert RecordingAsyncClient.calls == []
