from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.features.catalog.entities.price_item import (
    PriceImport,
    PriceImportRow,
    PriceItem,
    PriceItemDetail,
    PriceItemList,
    PriceItemSource,
)


class PriceItemNotFound(Exception):
    def __init__(self, item_id: UUID) -> None:
        super().__init__(f"Price item not found: {item_id}")
        self.item_id = item_id


class UnitOfWork(Protocol):
    async def __aenter__(self) -> UnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class PriceImportRepository(Protocol):
    async def add(self, price_import: PriceImport) -> None: ...

    async def update(self, price_import: PriceImport) -> None: ...

    async def add_row(self, row: PriceImportRow) -> None: ...

    async def update_row_item(self, row_id: UUID, item_id: UUID) -> None: ...

    async def find_imported_by_file_sha256(
        self,
        file_sha256: str,
    ) -> PriceImport | None: ...


class PriceItemRepository(Protocol):
    async def add(self, item: PriceItem) -> None: ...

    async def add_source(self, source: PriceItemSource) -> None: ...

    async def find_active_by_row_fingerprint(
        self,
        row_fingerprint: str,
    ) -> PriceItem | None: ...

    async def list_active(self, *, limit: int, offset: int) -> PriceItemList: ...

    async def get_with_sources(self, item_id: UUID) -> PriceItemDetail: ...


__all__ = [
    "PriceImportRepository",
    "PriceItemNotFound",
    "PriceItemRepository",
    "UnitOfWork",
]

