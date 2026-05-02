from collections.abc import Awaitable, Callable
from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SqlAlchemyUnitOfWork:
    session: AsyncSession

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._sessionmaker()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class SessionUnitOfWork:
    """UoW for a pre-created session (repos share the same session object)."""

    def __init__(
        self,
        session: AsyncSession,
        on_close: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._session = session
        self._on_close = on_close

    async def __aenter__(self) -> "SessionUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.rollback()
        finally:
            if self._on_close is not None:
                await self._on_close()
            await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


__all__ = ["SessionUnitOfWork", "SqlAlchemyUnitOfWork"]
