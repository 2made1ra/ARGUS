from types import TracebackType
from typing import Protocol, Self, runtime_checkable


@runtime_checkable
class UnitOfWork(Protocol):
    """Exiting without commit() rolls back.
    Exceptions inside the context block roll back automatically.
    """

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


__all__ = ["UnitOfWork"]
