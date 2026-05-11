from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.features.catalog.entities.price_item import PriceItem
from app.features.catalog.ports import (
    CatalogEmbeddingService,
    CatalogVectorIndex,
    CatalogVectorPoint,
    PriceItemIndexRepository,
    UnitOfWork,
)


@dataclass(slots=True)
class IndexPriceItemsResult:
    total: int = 0
    indexed: int = 0
    embedding_failed: int = 0
    indexing_failed: int = 0
    skipped: int = 0


class IndexPriceItemsUseCase:
    def __init__(
        self,
        *,
        items: PriceItemIndexRepository,
        embeddings: CatalogEmbeddingService,
        index: CatalogVectorIndex,
        uow: UnitOfWork,
        catalog_embedding_model: str,
        catalog_embedding_dim: int,
        catalog_embedding_template_version: str,
        catalog_document_prefix: str,
    ) -> None:
        self._items = items
        self._embeddings = embeddings
        self._index = index
        self._uow = uow
        self._catalog_embedding_model = catalog_embedding_model
        self._catalog_embedding_dim = catalog_embedding_dim
        self._catalog_embedding_template_version = catalog_embedding_template_version
        self._catalog_document_prefix = catalog_document_prefix

    async def execute(self, *, limit: int = 100) -> IndexPriceItemsResult:
        async with self._uow:
            items = await self._items.list_active_for_indexing(limit=limit)
            await self._uow.commit()

        result = IndexPriceItemsResult(total=len(items))
        for item in items:
            if not item.is_active:
                result.skipped += 1
                continue

            vector = await self._generate_vector(item)
            if vector is None:
                result.embedding_failed += 1
                continue

            point = CatalogVectorPoint(
                id=item.id,
                vector=vector,
                payload=_payload_from_item(
                    item,
                    embedding_model=self._catalog_embedding_model,
                    embedding_template_version=self._catalog_embedding_template_version,
                ),
            )
            try:
                await self._index.upsert_points([point])
            except Exception as exc:
                await self._mark_indexing_failed(item, str(exc))
                result.indexing_failed += 1
                continue

            await self._mark_indexed(item)
            result.indexed += 1

        return result

    async def _generate_vector(self, item: PriceItem) -> list[float] | None:
        embedding_input = f"{self._catalog_document_prefix}{item.embedding_text}"
        try:
            vectors = await self._embeddings.embed([embedding_input])
            vector = _single_vector(vectors)
            _validate_vector_dimension(vector, self._catalog_embedding_dim)
        except Exception as exc:
            await self._mark_embedding_failed(item, str(exc))
            return None
        return vector

    async def _mark_indexed(self, item: PriceItem) -> None:
        async with self._uow:
            await self._items.mark_indexed(
                item.id,
                embedding_model=self._catalog_embedding_model,
                embedding_template_version=self._catalog_embedding_template_version,
                indexed_at=datetime.now(UTC),
            )
            await self._uow.commit()

    async def _mark_embedding_failed(self, item: PriceItem, error: str) -> None:
        async with self._uow:
            await self._items.mark_embedding_failed(item.id, error=error)
            await self._uow.commit()

    async def _mark_indexing_failed(self, item: PriceItem, error: str) -> None:
        async with self._uow:
            await self._items.mark_indexing_failed(item.id, error=error)
            await self._uow.commit()


def _single_vector(vectors: list[list[float]]) -> list[float]:
    if len(vectors) != 1:
        raise ValueError(
            f"Embedding response count mismatch: expected 1, got {len(vectors)}",
        )
    return vectors[0]


def _validate_vector_dimension(vector: list[float], expected_dim: int) -> None:
    actual_dim = len(vector)
    if actual_dim != expected_dim:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dim}, got {actual_dim}",
        )


def _payload_from_item(
    item: PriceItem,
    *,
    embedding_model: str,
    embedding_template_version: str,
) -> dict[str, object]:
    return {
        "price_item_id": str(item.id),
        "import_batch_id": str(item.import_batch_id),
        "source_file_id": str(item.source_file_id),
        "category": item.category,
        "section": item.section,
        "unit": item.unit,
        "unit_price": _decimal_to_float(item.unit_price),
        "has_vat": item.has_vat,
        "vat_mode": item.vat_mode,
        "supplier": item.supplier,
        "supplier_city": item.supplier_city,
        "supplier_status": item.supplier_status,
        "embedding_model": embedding_model,
        "embedding_template_version": embedding_template_version,
    }


def _decimal_to_float(value: Decimal) -> float:
    return float(value)


__all__ = ["IndexPriceItemsResult", "IndexPriceItemsUseCase"]
