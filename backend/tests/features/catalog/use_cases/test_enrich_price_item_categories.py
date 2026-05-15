from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.features.catalog.entities.price_item import PriceItem
from app.features.catalog.ports import CatalogCategoryClassification
from app.features.catalog.use_cases.enrich_price_item_categories import (
    EnrichPriceItemCategoriesUseCase,
)


class FakeCategoryRepository:
    def __init__(self, items: list[PriceItem]) -> None:
        self.items = items
        self.enriched_calls: list[dict[str, Any]] = []
        self.failed_calls: list[dict[str, Any]] = []

    async def list_active_for_category_enrichment(
        self,
        *,
        limit: int,
    ) -> list[PriceItem]:
        return [
            item
            for item in self.items
            if item.is_active and item.category_enrichment_status == "pending"
        ][:limit]

    async def mark_category_enriched(
        self,
        item_id: UUID,
        *,
        service_category: str,
        confidence: float,
        reason: str | None,
        enriched_at: datetime,
        model: str,
        prompt_version: str,
        embedding_text: str,
    ) -> None:
        self.enriched_calls.append(
            {
                "item_id": item_id,
                "service_category": service_category,
                "confidence": confidence,
                "reason": reason,
                "enriched_at": enriched_at,
                "model": model,
                "prompt_version": prompt_version,
                "embedding_text": embedding_text,
            },
        )
        item = self._item(item_id)
        item.service_category = service_category
        item.service_category_confidence = confidence
        item.service_category_source = "llm"
        item.service_category_reason = reason
        item.category_enrichment_status = "enriched"
        item.category_enriched_at = enriched_at
        item.category_enrichment_model = model
        item.category_enrichment_prompt_version = prompt_version
        item.embedding_text = embedding_text

    async def mark_category_enrichment_failed(
        self,
        item_id: UUID,
        *,
        error: str,
        model: str,
        prompt_version: str,
    ) -> None:
        self.failed_calls.append(
            {
                "item_id": item_id,
                "error": error,
                "model": model,
                "prompt_version": prompt_version,
            },
        )
        item = self._item(item_id)
        item.category_enrichment_status = "failed"
        item.category_enrichment_error = error
        item.category_enrichment_model = model
        item.category_enrichment_prompt_version = prompt_version

    def _item(self, item_id: UUID) -> PriceItem:
        for item in self.items:
            if item.id == item_id:
                return item
        raise AssertionError(f"Unknown item {item_id}")


class FakeClassifier:
    def __init__(self, results: list[CatalogCategoryClassification]) -> None:
        self.results = results
        self.calls: list[list[PriceItem]] = []

    async def classify(
        self,
        items: list[PriceItem],
    ) -> list[CatalogCategoryClassification]:
        self.calls.append(items)
        return self.results


class FakeUoW:
    def __init__(self) -> None:
        self.commit_count = 0

    async def __aenter__(self) -> FakeUoW:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        return None


def _item() -> PriceItem:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return PriceItem(
        id=uuid4(),
        external_id="1",
        name="Акустическая система 600 Вт (аренда за 1 день)",
        category="Аренда",
        category_normalized="аренда",
        unit="день",
        unit_normalized="день",
        unit_price=Decimal("12000.00"),
        source_text="Акустическая система с коммутацией",
        section="Оборудование",
        section_normalized="оборудование",
        supplier=None,
        has_vat=None,
        vat_mode="unknown",
        supplier_inn=None,
        supplier_city=None,
        supplier_city_normalized=None,
        supplier_phone=None,
        supplier_email=None,
        supplier_status=None,
        supplier_status_normalized=None,
        import_batch_id=uuid4(),
        source_file_id=uuid4(),
        source_import_row_id=uuid4(),
        row_fingerprint="fingerprint",
        is_active=True,
        superseded_at=None,
        embedding_text="Название: Акустическая система 600 Вт\nКатегория: Аренда",
        embedding_model="nomic-embed-text-v1.5",
        embedding_template_version="prices_v1",
        catalog_index_status="indexed",
        embedding_error=None,
        indexing_error=None,
        indexed_at=now,
        legacy_embedding_present=False,
        legacy_embedding_dim=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_enriches_pending_items_and_resets_index_status() -> None:
    item = _item()
    repository = FakeCategoryRepository([item])
    classifier = FakeClassifier(
        [
            CatalogCategoryClassification(
                item_id=item.id,
                service_category="звук",
                confidence=0.93,
                reason="sound_equipment_name",
            ),
        ],
    )
    uow = FakeUoW()
    uc = EnrichPriceItemCategoriesUseCase(
        items=repository,
        classifier=classifier,
        uow=uow,
        model="qwen2.5",
    )

    result = await uc.execute(limit=10)

    assert result.total == 1
    assert result.enriched == 1
    assert classifier.calls == [[item]]
    assert item.service_category == "звук"
    assert item.category_enrichment_status == "enriched"
    assert item.catalog_index_status == "indexed"
    assert item.indexed_at is not None
    assert "Категория: звук" in item.embedding_text
    assert "аренда за 1 день" not in item.embedding_text
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_rejects_classifier_category_outside_taxonomy() -> None:
    item = _item()
    repository = FakeCategoryRepository([item])
    classifier = FakeClassifier(
        [
            CatalogCategoryClassification(
                item_id=item.id,
                service_category="неизвестно",
                confidence=0.5,
                reason="bad_enum",
            ),
        ],
    )
    uc = EnrichPriceItemCategoriesUseCase(
        items=repository,
        classifier=classifier,
        uow=FakeUoW(),
        model="qwen2.5",
    )

    result = await uc.execute(limit=10)

    assert result.failed == 1
    assert repository.enriched_calls == []
    assert "Unknown service category" in repository.failed_calls[0]["error"]
