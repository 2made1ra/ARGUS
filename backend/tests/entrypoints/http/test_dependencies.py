"""Regression tests for HTTP dependency resource cleanup."""
from __future__ import annotations

from collections.abc import Callable

import pytest
from app.config import Settings
from app.entrypoints.http import session as http_session


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

    dep = http_session._session()
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

    dep = http_session.get_qdrant_client(settings)
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

    dep = http_session.get_qdrant_client(settings)
    yielded = await anext(dep)

    with pytest.raises(RuntimeError, match="request failed"):
        await dep.athrow(RuntimeError("request failed"))

    assert yielded is client
    assert client.closed is True
