from __future__ import annotations

from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

from app.features.catalog.ports import CatalogSearchFilters, CatalogSearchHit


class QdrantCatalogSearch:
    def __init__(self, client: AsyncQdrantClient, collection: str) -> None:
        self._client = client
        self._collection = collection

    async def search(
        self,
        *,
        query_vector: list[float],
        filters: CatalogSearchFilters | None,
        limit: int,
    ) -> list[CatalogSearchHit]:
        response = await self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            query_filter=_filter_from_catalog_filters(filters),
            limit=limit,
            with_payload=True,
        )
        return [_hit_from_qdrant(hit) for hit in response.points]


def _filter_from_catalog_filters(filters: CatalogSearchFilters | None) -> Filter | None:
    if filters is None:
        return None

    conditions: list[FieldCondition] = []
    exact_values: tuple[tuple[str, Any | None], ...] = (
        ("price_item_id", _optional_uuid(filters.price_item_id)),
        ("import_batch_id", _optional_uuid(filters.import_batch_id)),
        ("source_file_id", _optional_uuid(filters.source_file_id)),
        ("category", filters.category),
        ("section", filters.section),
        ("unit", filters.unit),
        ("has_vat", filters.has_vat),
        ("vat_mode", filters.vat_mode),
        ("supplier_city", filters.supplier_city),
        ("supplier_status", filters.supplier_status),
        ("embedding_template_version", filters.embedding_template_version),
    )
    for key, value in exact_values:
        if value is not None:
            conditions.append(
                FieldCondition(
                    key=key,
                    match=MatchValue(value=value),
                ),
            )

    if filters.unit_price is not None:
        conditions.append(
            FieldCondition(
                key="unit_price",
                range=Range(gte=filters.unit_price, lte=filters.unit_price),
            ),
        )
    elif filters.unit_price_min is not None or filters.unit_price_max is not None:
        conditions.append(
            FieldCondition(
                key="unit_price",
                range=Range(gte=filters.unit_price_min, lte=filters.unit_price_max),
            ),
        )

    if not conditions:
        return None
    return Filter(must=conditions)


def _hit_from_qdrant(hit: Any) -> CatalogSearchHit:
    payload = dict(hit.payload or {})
    price_item_id = _uuid_from_value(payload.get("price_item_id", hit.id))
    return CatalogSearchHit(
        price_item_id=price_item_id,
        score=float(hit.score),
        payload=payload,
    )


def _optional_uuid(value: UUID | None) -> str | None:
    return str(value) if value is not None else None


def _uuid_from_value(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


__all__ = ["QdrantCatalogSearch"]
