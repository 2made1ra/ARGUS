from __future__ import annotations

import pytest
from app import main
from app.config import Settings
from fastapi import FastAPI


class _FakeQdrantClient:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        qdrant_url="http://localhost:6333",
        lm_studio_url="http://localhost:1234/v1",
        lm_studio_llm_model="test-model",
    )


async def test_lifespan_closes_qdrant_client_after_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeQdrantClient()
    bootstrap_calls: list[tuple[object, str, int]] = []

    async def fake_bootstrap_collection(
        qdrant: object,
        collection: str,
        dim: int,
    ) -> None:
        bootstrap_calls.append((qdrant, collection, dim))
        assert client.closed is False

    monkeypatch.setattr(main, "get_settings", _settings)
    monkeypatch.setattr(main, "make_qdrant_client", lambda url: client)
    monkeypatch.setattr(main, "bootstrap_collection", fake_bootstrap_collection)

    async with main.lifespan(FastAPI()):
        assert client.closed is True

    assert bootstrap_calls == [(client, "document_chunks", 768)]
