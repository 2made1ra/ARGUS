from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.features.catalog.entities.price_item import PriceItem
from app.features.catalog.ports import CatalogVectorPoint
from app.features.catalog.use_cases.index_price_items import (
    IndexPriceItemsProgress,
    IndexPriceItemsUseCase,
)


class FakePriceItemIndexRepository:
    def __init__(
        self,
        items: list[PriceItem],
        legacy_vectors: dict[UUID, list[float] | None] | None = None,
    ) -> None:
        self.items = items
        self.legacy_vectors = legacy_vectors or {
            item.id: [0.1, 0.2, 0.3] for item in items
        }
        self.indexed_calls: list[dict[str, Any]] = []
        self.embedding_failed_calls: list[dict[str, Any]] = []
        self.indexing_failed_calls: list[dict[str, Any]] = []

    async def list_active_for_indexing(
        self,
        *,
        limit: int | None,
        import_batch_id: UUID | None = None,
    ) -> list[PriceItem]:
        items = self.items
        if import_batch_id is not None:
            items = [item for item in items if item.import_batch_id == import_batch_id]
        if limit is None:
            return items
        return items[:limit]

    async def get_legacy_embedding(self, item_id: UUID) -> list[float] | None:
        return self.legacy_vectors.get(item_id)

    async def mark_indexed(
        self,
        item_id: UUID,
        *,
        embedding_model: str,
        embedding_template_version: str,
        indexed_at: datetime,
    ) -> None:
        self.indexed_calls.append(
            {
                "item_id": item_id,
                "embedding_model": embedding_model,
                "embedding_template_version": embedding_template_version,
                "indexed_at": indexed_at,
            },
        )
        item = self._item(item_id)
        item.catalog_index_status = "indexed"
        item.embedding_model = embedding_model
        item.embedding_template_version = embedding_template_version
        item.embedding_error = None
        item.indexing_error = None
        item.indexed_at = indexed_at

    async def mark_embedding_failed(self, item_id: UUID, *, error: str) -> None:
        self.embedding_failed_calls.append({"item_id": item_id, "error": error})
        item = self._item(item_id)
        item.catalog_index_status = "embedding_failed"
        item.embedding_error = error
        item.indexing_error = None

    async def mark_indexing_failed(self, item_id: UUID, *, error: str) -> None:
        self.indexing_failed_calls.append({"item_id": item_id, "error": error})
        item = self._item(item_id)
        item.catalog_index_status = "indexing_failed"
        item.embedding_error = None
        item.indexing_error = error

    def _item(self, item_id: UUID) -> PriceItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise AssertionError(f"Unknown item {item_id}")


class FakeCatalogIndex:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.points: list[CatalogVectorPoint] = []

    async def upsert_points(self, points: list[CatalogVectorPoint]) -> None:
        self.points.extend(points)
        if self.error is not None:
            raise self.error


class FakeUoW:
    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0

    async def __aenter__(self) -> FakeUoW:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


def _item(*, is_active: bool = True) -> PriceItem:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return PriceItem(
        id=uuid4(),
        external_id="10",
        name="Аренда света",
        category="Аренда",
        category_normalized="аренда",
        unit="день",
        unit_normalized="день",
        unit_price=Decimal("15000.00"),
        source_text="Комплект света для сцены",
        section="Свет",
        section_normalized="свет",
        supplier="ООО Ромашка",
        has_vat="Без НДС",
        vat_mode="without_vat",
        supplier_inn="7701234567",
        supplier_city="г. Москва",
        supplier_city_normalized="москва",
        supplier_phone="+7",
        supplier_email="info@example.com",
        supplier_status="Активен",
        supplier_status_normalized="активен",
        import_batch_id=uuid4(),
        source_file_id=uuid4(),
        source_import_row_id=uuid4(),
        row_fingerprint="fingerprint",
        is_active=is_active,
        superseded_at=None,
        embedding_text="Название: Аренда света\nКатегория: Аренда",
        embedding_model="legacy-csv-model",
        embedding_template_version="prices_v1",
        catalog_index_status="pending",
        embedding_error=None,
        indexing_error=None,
        indexed_at=None,
        legacy_embedding_present=True,
        legacy_embedding_dim=1536,
        created_at=now,
        updated_at=now,
    )


def _use_case(
    *,
    items: list[PriceItem],
    legacy_vectors: dict[UUID, list[float] | None] | None = None,
    index: FakeCatalogIndex | None = None,
) -> tuple[
    IndexPriceItemsUseCase,
    FakePriceItemIndexRepository,
    FakeCatalogIndex,
    FakeUoW,
]:
    repository = FakePriceItemIndexRepository(items, legacy_vectors)
    catalog_index = index if index is not None else FakeCatalogIndex()
    uow = FakeUoW()
    return (
        IndexPriceItemsUseCase(
            items=repository,
            index=catalog_index,
            uow=uow,
            catalog_embedding_model="text-embedding-3-small",
            catalog_embedding_dim=3,
            catalog_embedding_template_version="legacy_csv_embedding",
        ),
        repository,
        catalog_index,
        uow,
    )


@pytest.mark.asyncio
async def test_indexes_active_item_with_legacy_csv_embedding() -> None:
    item = _item()
    uc, repository, index, uow = _use_case(
        items=[item],
        legacy_vectors={item.id: [0.4, 0.5, 0.6]},
    )

    result = await uc.execute(limit=10)

    assert result.indexed == 1
    assert len(index.points) == 1
    point = index.points[0]
    assert point.id == item.id
    assert point.vector == [0.4, 0.5, 0.6]
    assert point.payload == {
        "price_item_id": str(item.id),
        "import_batch_id": str(item.import_batch_id),
        "source_file_id": str(item.source_file_id),
        "category": "Аренда",
        "category_normalized": "аренда",
        "service_category": None,
        "section": "Свет",
        "section_normalized": "свет",
        "unit": "день",
        "unit_price": 15000.0,
        "has_vat": "Без НДС",
        "vat_mode": "without_vat",
        "supplier": "ООО Ромашка",
        "supplier_city": "г. Москва",
        "supplier_city_normalized": "москва",
        "supplier_status": "Активен",
        "supplier_status_normalized": "активен",
        "embedding_model": "text-embedding-3-small",
        "embedding_template_version": "legacy_csv_embedding",
    }
    assert "legacy_embedding_dim" not in point.payload
    assert "legacy_embedding_present" not in point.payload
    assert item.catalog_index_status == "indexed"
    assert item.embedding_error is None
    assert item.indexing_error is None
    assert item.indexed_at is not None
    assert repository.indexed_calls[0]["embedding_model"] == "text-embedding-3-small"
    assert uow.commit_count == 2


@pytest.mark.asyncio
async def test_index_price_items_supports_unlimited_progress_callback() -> None:
    first = _item()
    second = _item()
    uc, _repository, _index, _uow = _use_case(items=[first, second])
    events: list[IndexPriceItemsProgress] = []

    async def capture(event: IndexPriceItemsProgress) -> None:
        events.append(event)

    result = await uc.execute(limit=None, progress_callback=capture)

    assert result.total == 2
    assert result.indexed == 2
    assert [event.processed for event in events] == [1, 2, 2]
    assert all(event.total == 2 for event in events)
    assert events[-1].done is True
    assert events[-1].indexed == 2


@pytest.mark.asyncio
async def test_index_price_items_can_scope_to_import_batch() -> None:
    target_batch_id = uuid4()
    target = _item()
    target.import_batch_id = target_batch_id
    other = _item()
    uc, _repository, index, _uow = _use_case(items=[target, other])

    result = await uc.execute(limit=None, import_batch_id=target_batch_id)

    assert result.total == 1
    assert result.indexed == 1
    assert [point.id for point in index.points] == [target.id]


@pytest.mark.asyncio
async def test_marks_embedding_failed_when_legacy_embedding_is_missing() -> None:
    item = _item()
    uc, repository, index, _uow = _use_case(
        items=[item],
        legacy_vectors={item.id: None},
    )

    result = await uc.execute(limit=10)

    assert result.embedding_failed == 1
    assert index.points == []
    assert item.catalog_index_status == "embedding_failed"
    assert item.embedding_error == "Legacy CSV embedding is missing"
    assert item.indexing_error is None
    assert repository.embedding_failed_calls == [
        {"item_id": item.id, "error": "Legacy CSV embedding is missing"},
    ]


@pytest.mark.asyncio
async def test_marks_embedding_failed_when_vector_dimension_is_not_catalog_dim(
) -> None:
    item = _item()
    uc, _repository, index, _uow = _use_case(
        items=[item],
        legacy_vectors={item.id: [0.1, 0.2]},
    )

    result = await uc.execute(limit=10)

    assert result.embedding_failed == 1
    assert index.points == []
    assert item.catalog_index_status == "embedding_failed"
    assert item.embedding_error == "Embedding dimension mismatch: expected 3, got 2"
    assert item.indexing_error is None


@pytest.mark.asyncio
async def test_marks_indexing_failed_when_qdrant_upsert_fails_after_embedding() -> None:
    item = _item()
    uc, repository, index, _uow = _use_case(
        items=[item],
        index=FakeCatalogIndex(error=RuntimeError("qdrant unavailable")),
    )

    result = await uc.execute(limit=10)

    assert result.indexing_failed == 1
    assert len(index.points) == 1
    assert item.catalog_index_status == "indexing_failed"
    assert item.embedding_error is None
    assert item.indexing_error == "qdrant unavailable"
    assert repository.indexing_failed_calls == [
        {"item_id": item.id, "error": "qdrant unavailable"},
    ]


@pytest.mark.asyncio
async def test_skips_inactive_rows_without_embedding_or_indexing() -> None:
    item = _item(is_active=False)
    uc, repository, index, _uow = _use_case(items=[item])

    result = await uc.execute(limit=10)

    assert result.skipped == 1
    assert index.points == []
    assert repository.indexed_calls == []
    assert item.catalog_index_status == "pending"
