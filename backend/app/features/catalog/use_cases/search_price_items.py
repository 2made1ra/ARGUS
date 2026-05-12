from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.features.catalog.dto import (
    FoundPriceItem,
    MatchReason,
    MatchReasonCode,
    SearchPriceItemsFilters,
    SearchPriceItemsResult,
)
from app.features.catalog.entities.price_item import PriceItem
from app.features.catalog.ports import (
    CatalogEmbeddingService,
    CatalogSearchFilters,
    CatalogSearchHit,
    CatalogVectorSearch,
    PriceItemSearchRepository,
)

_SNIPPET_LENGTH = 96


class SearchPriceItemsUseCase:
    def __init__(
        self,
        *,
        items: PriceItemSearchRepository,
        embeddings: CatalogEmbeddingService,
        vector_search: CatalogVectorSearch,
        catalog_query_prefix: str,
        catalog_embedding_template_version: str,
    ) -> None:
        self._items = items
        self._embeddings = embeddings
        self._vector_search = vector_search
        self._catalog_query_prefix = catalog_query_prefix
        self._catalog_embedding_template_version = catalog_embedding_template_version

    async def execute(
        self,
        *,
        query: str,
        filters: SearchPriceItemsFilters | None = None,
        limit: int = 10,
    ) -> SearchPriceItemsResult:
        return await self.search_items(query=query, filters=filters, limit=limit)

    async def search_items(
        self,
        *,
        query: str,
        filters: SearchPriceItemsFilters | None = None,
        limit: int = 10,
    ) -> SearchPriceItemsResult:
        query = query.strip()
        if not query or limit < 1:
            return SearchPriceItemsResult(items=[])

        filters = filters or SearchPriceItemsFilters()
        semantic_hits = await self._semantic_hits(
            query=query,
            filters=filters,
            limit=limit,
        )
        keyword_hits = await self._items.search_active_by_keywords(
            query=query,
            filters=filters,
            limit=limit,
        )
        candidates = _merge_candidates(semantic_hits, keyword_hits, limit=limit)
        if not candidates:
            return SearchPriceItemsResult(items=[])

        hydrated = await self._items.list_active_by_ids(
            [candidate.item_id for candidate in candidates],
            filters=filters,
        )
        items_by_id = {item.id: item for item in hydrated}

        found_items: list[FoundPriceItem] = []
        for candidate in candidates:
            item = items_by_id.get(candidate.item_id)
            if item is None:
                continue
            found_items.append(_found_item(item, candidate))

        return SearchPriceItemsResult(items=found_items)

    async def _semantic_hits(
        self,
        *,
        query: str,
        filters: SearchPriceItemsFilters,
        limit: int,
    ) -> list[CatalogSearchHit]:
        query_input = f"{self._catalog_query_prefix}{query}"
        vectors = await self._embeddings.embed([query_input])
        vector = _single_vector(vectors)
        return await self._vector_search.search(
            query_vector=vector,
            filters=_catalog_filters_from_search_filters(
                filters,
                embedding_template_version=self._catalog_embedding_template_version,
            ),
            limit=limit,
        )


class _Candidate:
    def __init__(
        self,
        *,
        item_id: UUID,
        score: float,
        reason_code: MatchReasonCode,
    ) -> None:
        self.item_id = item_id
        self.score = score
        self.reason_code = reason_code


def _merge_candidates(
    semantic_hits: list[CatalogSearchHit],
    keyword_hits: list[tuple[UUID, float, MatchReasonCode]],
    *,
    limit: int,
) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    seen: set[UUID] = set()

    for hit in semantic_hits:
        if hit.price_item_id in seen:
            continue
        candidates.append(
            _Candidate(
                item_id=hit.price_item_id,
                score=hit.score,
                reason_code="semantic",
            ),
        )
        seen.add(hit.price_item_id)
        if len(candidates) >= limit:
            return candidates

    for item_id, score, reason_code in keyword_hits:
        if item_id in seen:
            continue
        candidates.append(
            _Candidate(
                item_id=item_id,
                score=score,
                reason_code=reason_code,
            ),
        )
        seen.add(item_id)
        if len(candidates) >= limit:
            break

    return candidates


def _catalog_filters_from_search_filters(
    filters: SearchPriceItemsFilters,
    *,
    embedding_template_version: str,
) -> CatalogSearchFilters:
    return CatalogSearchFilters(
        category=filters.category,
        unit_price=_decimal_to_float(filters.unit_price),
        unit_price_min=_decimal_to_float(filters.unit_price_min),
        unit_price_max=_decimal_to_float(filters.unit_price_max),
        has_vat=filters.has_vat,
        vat_mode=filters.vat_mode,
        supplier_city=filters.supplier_city,
        supplier_city_normalized=filters.supplier_city_normalized,
        supplier_status=filters.supplier_status,
        supplier_status_normalized=filters.supplier_status_normalized,
        embedding_template_version=embedding_template_version,
    )


def _found_item(item: PriceItem, candidate: _Candidate) -> FoundPriceItem:
    return FoundPriceItem(
        id=item.id,
        score=candidate.score,
        name=item.name,
        category=item.category,
        unit=item.unit,
        unit_price=item.unit_price,
        supplier=item.supplier,
        supplier_city=item.supplier_city,
        source_text_snippet=_source_text_snippet(item.source_text),
        source_text_full_available=item.source_text is not None,
        match_reason=MatchReason(
            code=candidate.reason_code,
            label=_match_reason_label(candidate.reason_code),
        ),
    )


def _source_text_snippet(source_text: str | None) -> str | None:
    if source_text is None:
        return None
    normalized = " ".join(source_text.split())
    if not normalized:
        return None
    if len(normalized) <= _SNIPPET_LENGTH:
        return normalized
    return f"{normalized[: _SNIPPET_LENGTH - 3].rstrip()}..."


def _match_reason_label(code: MatchReasonCode) -> str:
    labels: dict[MatchReasonCode, str] = {
        "semantic": "Семантическое совпадение с запросом",
        "keyword_name": "Совпадение по названию позиции",
        "keyword_supplier": "Совпадение по поставщику",
        "keyword_inn": "Совпадение по ИНН поставщика",
        "keyword_source_text": "Совпадение по исходному описанию",
        "keyword_external_id": "Совпадение по внешнему идентификатору",
    }
    return labels[code]


def _single_vector(vectors: list[list[float]]) -> list[float]:
    if len(vectors) != 1:
        raise ValueError(
            f"Embedding response count mismatch: expected 1, got {len(vectors)}",
        )
    return vectors[0]


def _decimal_to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


__all__ = ["SearchPriceItemsResult", "SearchPriceItemsUseCase"]
