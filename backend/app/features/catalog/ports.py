from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.features.catalog.dto import (
    MatchReasonCode,
    SearchPriceItemsFilters,
    SearchPriceItemsResult,
)
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


class PriceItemIndexRepository(Protocol):
    async def list_active_for_indexing(self, *, limit: int) -> list[PriceItem]: ...

    async def mark_indexed(
        self,
        item_id: UUID,
        *,
        embedding_model: str,
        embedding_template_version: str,
        indexed_at: datetime,
    ) -> None: ...

    async def mark_embedding_failed(self, item_id: UUID, *, error: str) -> None: ...

    async def mark_indexing_failed(self, item_id: UUID, *, error: str) -> None: ...


class PriceItemSearchRepository(Protocol):
    async def search_active_by_keywords(
        self,
        *,
        query: str,
        filters: SearchPriceItemsFilters,
        limit: int,
    ) -> list[tuple[UUID, float, MatchReasonCode]]: ...

    async def list_active_by_ids(
        self,
        item_ids: list[UUID],
        *,
        filters: SearchPriceItemsFilters,
    ) -> list[PriceItem]: ...


@dataclass(slots=True)
class CatalogVectorPoint:
    id: UUID
    vector: list[float]
    payload: dict[str, Any]


@dataclass(slots=True)
class CatalogSearchFilters:
    price_item_id: UUID | None = None
    import_batch_id: UUID | None = None
    source_file_id: UUID | None = None
    category: str | None = None
    section: str | None = None
    unit: str | None = None
    unit_price: float | None = None
    unit_price_min: float | None = None
    unit_price_max: float | None = None
    has_vat: str | None = None
    vat_mode: str | None = None
    supplier_city: str | None = None
    supplier_status: str | None = None
    embedding_template_version: str | None = None


@dataclass(slots=True)
class CatalogSearchHit:
    price_item_id: UUID
    score: float
    payload: dict[str, Any]


class CatalogEmbeddingService(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class CatalogVectorIndex(Protocol):
    async def upsert_points(self, points: list[CatalogVectorPoint]) -> None: ...


class CatalogVectorSearch(Protocol):
    async def search(
        self,
        *,
        query_vector: list[float],
        filters: CatalogSearchFilters | None,
        limit: int,
    ) -> list[CatalogSearchHit]: ...


class SearchItemsService(Protocol):
    async def search_items(
        self,
        *,
        query: str,
        filters: SearchPriceItemsFilters | None = None,
        limit: int = 10,
    ) -> SearchPriceItemsResult: ...


__all__ = [
    "CatalogEmbeddingService",
    "CatalogSearchFilters",
    "CatalogSearchHit",
    "CatalogVectorIndex",
    "CatalogVectorPoint",
    "CatalogVectorSearch",
    "PriceImportRepository",
    "PriceItemNotFound",
    "PriceItemIndexRepository",
    "PriceItemRepository",
    "PriceItemSearchRepository",
    "SearchItemsService",
    "UnitOfWork",
]
