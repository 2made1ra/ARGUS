from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.core.domain.service_taxonomy import validate_service_category
from app.features.catalog.embedding_text import build_embedding_text
from app.features.catalog.entities.price_item import PriceItem
from app.features.catalog.ports import (
    CatalogCategoryClassification,
    CatalogCategoryClassifier,
    PriceItemCategoryEnrichmentRepository,
    UnitOfWork,
)

PROMPT_VERSION = "catalog_service_category_v1"


@dataclass(slots=True)
class EnrichPriceItemCategoriesResult:
    total: int = 0
    enriched: int = 0
    failed: int = 0


class EnrichPriceItemCategoriesUseCase:
    def __init__(
        self,
        *,
        items: PriceItemCategoryEnrichmentRepository,
        classifier: CatalogCategoryClassifier,
        uow: UnitOfWork,
        model: str,
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        self._items = items
        self._classifier = classifier
        self._uow = uow
        self._model = model
        self._prompt_version = prompt_version

    async def execute(self, *, limit: int = 100) -> EnrichPriceItemCategoriesResult:
        if limit < 1:
            return EnrichPriceItemCategoriesResult()

        async with self._uow:
            items = await self._items.list_active_for_category_enrichment(limit=limit)
            result = EnrichPriceItemCategoriesResult(total=len(items))
            if not items:
                await self._uow.commit()
                return result

            classifications = {
                classification.item_id: classification
                for classification in await self._classifier.classify(items)
            }
            for item in items:
                classification = classifications.get(item.id)
                if classification is None:
                    await self._mark_failed(item.id, "classifier omitted item")
                    result.failed += 1
                    continue

                try:
                    await self._mark_enriched(item, classification)
                except ValueError as exc:
                    await self._mark_failed(item.id, str(exc))
                    result.failed += 1
                    continue
                result.enriched += 1

            await self._uow.commit()
            return result

    async def _mark_enriched(
        self,
        item: PriceItem,
        classification: CatalogCategoryClassification,
    ) -> None:
        service_category = validate_service_category(classification.service_category)
        embedding_text = build_embedding_text(
            name=item.name,
            category=item.category,
            service_category=service_category,
            section=item.section,
            source_text=item.source_text,
            unit=item.unit_normalized or item.unit,
        )
        await self._items.mark_category_enriched(
            classification.item_id,
            service_category=service_category,
            confidence=classification.confidence,
            reason=classification.reason,
            enriched_at=datetime.now(UTC),
            model=self._model,
            prompt_version=self._prompt_version,
            embedding_text=embedding_text,
        )

    async def _mark_failed(self, item_id: UUID, error: str) -> None:
        await self._items.mark_category_enrichment_failed(
            item_id,
            error=error,
            model=self._model,
            prompt_version=self._prompt_version,
        )


__all__ = [
    "EnrichPriceItemCategoriesResult",
    "EnrichPriceItemCategoriesUseCase",
    "PROMPT_VERSION",
]
