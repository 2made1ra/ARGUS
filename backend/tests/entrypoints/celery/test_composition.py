from __future__ import annotations

import pytest
from app.config import Settings
from app.entrypoints.celery import composition
from app.features.ingest.use_cases.index_document import IndexDocumentUseCase


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


async def test_build_index_uc_closes_qdrant_client_after_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeQdrantClient()

    monkeypatch.setattr(composition, "get_settings", _settings)
    monkeypatch.setattr(composition, "_session", object)
    monkeypatch.setattr(composition, "make_qdrant_client", lambda url: client)

    async with composition.build_index_uc() as use_case:
        assert isinstance(use_case, IndexDocumentUseCase)
        assert client.closed is False

    assert client.closed is True


async def test_build_index_uc_closes_qdrant_client_after_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeQdrantClient()

    monkeypatch.setattr(composition, "get_settings", _settings)
    monkeypatch.setattr(composition, "_session", object)
    monkeypatch.setattr(composition, "make_qdrant_client", lambda url: client)

    with pytest.raises(RuntimeError, match="index failed"):
        async with composition.build_index_uc():
            raise RuntimeError("index failed")

    assert client.closed is True
