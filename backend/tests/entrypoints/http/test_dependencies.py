"""Regression tests for HTTP dependency resource cleanup."""
from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator, Callable
from typing import Annotated, Any, cast

import pytest
from app.config import Settings
from app.entrypoints.http import dependencies
from app.entrypoints.http import session as http_session
from app.features.catalog.use_cases.search_price_items import SearchPriceItemsUseCase
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient


class _FakeSession:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _FakeQdrantClient:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


async def test_session_dependency_closes_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()

    def fake_sessionmaker() -> Callable[[], _FakeSession]:
        return lambda: session

    monkeypatch.setattr(http_session, "get_sessionmaker", fake_sessionmaker)

    dep = cast(AsyncGenerator[Any], http_session._session())
    yielded = await anext(dep)
    await dep.aclose()

    assert yielded is session
    assert session.closed is True


async def test_qdrant_dependency_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeQdrantClient()
    settings = Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        qdrant_url="http://localhost:6333",
        lm_studio_url="http://localhost:1234/v1",
        lm_studio_llm_model="test-model",
    )

    monkeypatch.setattr(http_session, "make_qdrant_client", lambda url: client)

    dep = cast(AsyncGenerator[Any], http_session.get_qdrant_client(settings))
    yielded = await anext(dep)
    await dep.aclose()

    assert yielded is client
    assert client.closed is True


async def test_qdrant_dependency_closes_client_after_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeQdrantClient()
    settings = Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        qdrant_url="http://localhost:6333",
        lm_studio_url="http://localhost:1234/v1",
        lm_studio_llm_model="test-model",
    )

    monkeypatch.setattr(http_session, "make_qdrant_client", lambda url: client)

    dep = cast(AsyncGenerator[Any], http_session.get_qdrant_client(settings))
    yielded = await anext(dep)

    with pytest.raises(RuntimeError, match="request failed"):
        await dep.athrow(RuntimeError("request failed"))

    assert yielded is client
    assert client.closed is True


def test_demo_search_dependency_does_not_create_llm_embeddings_or_qdrant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        qdrant_url="http://localhost:6333",
        lm_studio_url="http://localhost:1234/v1",
        lm_studio_llm_model="test-model",
        argus_demo_mode=True,
    )

    async def fake_session() -> AsyncIterator[object]:
        yield object()

    async def fail_qdrant_client() -> AsyncIterator[object]:
        raise AssertionError("Qdrant dependency should not be resolved in demo mode")
        yield object()

    def fail_constructor(*args: object, **kwargs: object) -> object:
        raise AssertionError("LLM embeddings or Qdrant search should not be created")

    monkeypatch.setattr(dependencies, "LMStudioEmbeddings", fail_constructor)
    monkeypatch.setattr(dependencies, "QdrantCatalogSearch", fail_constructor)

    app = FastAPI()
    app.dependency_overrides[dependencies.get_settings] = lambda: settings
    app.dependency_overrides[dependencies._session] = fake_session
    app.dependency_overrides[dependencies.get_qdrant_client] = fail_qdrant_client

    @app.get("/probe")
    async def probe(
        uc: Annotated[
            SearchPriceItemsUseCase,
            Depends(dependencies.get_search_price_items_uc),
        ],
    ) -> dict[str, bool]:
        return {
            "semantic_search_enabled": bool(
                uc._semantic_search_enabled,
            ),
        }

    response = TestClient(app).get("/probe")

    assert response.status_code == 200
    assert response.json() == {"semantic_search_enabled": False}


def test_demo_chat_dependency_does_not_create_lm_router_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        qdrant_url="http://localhost:6333",
        lm_studio_url="http://localhost:1234/v1",
        lm_studio_llm_model="test-model",
        argus_demo_mode=True,
    )

    def fail_lm_router_adapter(*args: object, **kwargs: object) -> object:
        raise AssertionError("LM router adapter should not be created in demo mode")

    monkeypatch.setattr(
        dependencies,
        "LMStudioAssistantRouterAdapter",
        fail_lm_router_adapter,
    )

    dependencies.get_chat_turn_uc(
        settings=settings,
        search=cast(Any, object()),
        details=cast(Any, object()),
    )
