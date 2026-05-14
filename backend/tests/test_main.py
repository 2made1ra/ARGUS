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


def _demo_settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        qdrant_url="http://localhost:6333",
        lm_studio_url="http://localhost:1234/v1",
        lm_studio_llm_model="test-model",
        argus_demo_mode=True,
    )


async def test_lifespan_closes_qdrant_client_after_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeQdrantClient()
    bootstrap_calls: list[dict[str, object]] = []

    async def fake_bootstrap_qdrant_collections(
        qdrant: object,
        *,
        document_collection: str,
        document_dim: int,
        catalog_collection: str,
        catalog_dim: int,
    ) -> None:
        bootstrap_calls.append(
            {
                "qdrant": qdrant,
                "document_collection": document_collection,
                "document_dim": document_dim,
                "catalog_collection": catalog_collection,
                "catalog_dim": catalog_dim,
            },
        )
        assert client.closed is False

    monkeypatch.setattr(main, "get_settings", _settings)
    monkeypatch.setattr(main, "make_qdrant_client", lambda url: client)
    monkeypatch.setattr(
        main,
        "bootstrap_qdrant_collections",
        fake_bootstrap_qdrant_collections,
    )

    async with main.lifespan(FastAPI()):
        assert client.closed is True

    assert bootstrap_calls == [
        {
            "qdrant": client,
            "document_collection": "document_chunks",
            "document_dim": 768,
            "catalog_collection": "price_items_search_v1",
            "catalog_dim": 768,
        },
    ]


async def test_lifespan_skips_qdrant_bootstrap_in_demo_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    qdrant_client_calls: list[str] = []
    bootstrap_calls: list[str] = []

    def fail_make_qdrant_client(url: str) -> object:
        qdrant_client_calls.append(url)
        raise AssertionError("Qdrant client should not be created in demo mode")

    async def fail_bootstrap_qdrant_collections(
        *args: object,
        **kwargs: object,
    ) -> None:
        bootstrap_calls.append("called")
        raise AssertionError("Qdrant bootstrap should not run in demo mode")

    monkeypatch.setattr(main, "get_settings", _demo_settings)
    monkeypatch.setattr(main, "make_qdrant_client", fail_make_qdrant_client)
    monkeypatch.setattr(
        main,
        "bootstrap_qdrant_collections",
        fail_bootstrap_qdrant_collections,
    )

    async with main.lifespan(FastAPI()):
        pass

    assert qdrant_client_calls == []
    assert bootstrap_calls == []
