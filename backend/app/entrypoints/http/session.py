from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.qdrant.client import make_qdrant_client
from app.adapters.sqlalchemy.session import make_engine, make_sessionmaker
from app.config import Settings, get_settings


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return make_sessionmaker(make_engine(get_settings().database_url))


async def _session() -> AsyncIterator[AsyncSession]:
    """Fresh session per request; closed after FastAPI resolves dependencies."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        await session.close()


async def get_qdrant_client(
    settings: Settings = Depends(get_settings),
) -> AsyncIterator[AsyncQdrantClient]:
    qdrant = make_qdrant_client(settings.qdrant_url)
    try:
        yield qdrant
    finally:
        await qdrant.close()


__all__ = ["_session", "get_qdrant_client", "get_sessionmaker"]
