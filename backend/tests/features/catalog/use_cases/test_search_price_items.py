from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.features.catalog.domain.keyword_search import (
    build_keyword_query,
    keyword_reason_for_fields,
    keyword_score,
    price_item_keyword_fields,
    price_item_matches_filters,
)
from app.features.catalog.dto import MatchReasonCode, SearchPriceItemsFilters
from app.features.catalog.entities.price_item import PriceItem
from app.features.catalog.ports import CatalogSearchFilters, CatalogSearchHit
from app.features.catalog.use_cases.import_prices_csv import ImportPricesCsvUseCase
from app.features.catalog.use_cases.search_price_items import SearchPriceItemsUseCase


class _FakeImportRepository:
    def __init__(self) -> None:
        self.imports: list[Any] = []
        self.rows: list[Any] = []

    async def add(self, price_import: Any) -> None:
        self.imports.append(price_import)

    async def update(self, price_import: Any) -> None:
        self.imports = [
            price_import if item.id == price_import.id else item
            for item in self.imports
        ]

    async def add_row(self, row: Any) -> None:
        self.rows.append(row)

    async def update_row_item(self, row_id: UUID, item_id: UUID) -> None:
        for row in self.rows:
            if row.id == row_id:
                row.price_item_id = item_id

    async def find_imported_by_file_sha256(self, file_sha256: str) -> Any | None:
        for price_import in self.imports:
            if (
                price_import.file_sha256 == file_sha256
                and price_import.status == "IMPORTED"
            ):
                return price_import
        return None


class _FakeImportItemRepository:
    def __init__(self) -> None:
        self.items: list[PriceItem] = []
        self.sources: list[Any] = []

    async def add(self, item: PriceItem) -> None:
        self.items.append(item)

    async def add_source(self, source: Any) -> None:
        self.sources.append(source)

    async def find_active_by_row_fingerprint(
        self,
        row_fingerprint: str,
    ) -> PriceItem | None:
        for item in self.items:
            if item.row_fingerprint == row_fingerprint and item.is_active:
                return item
        return None


class _FakeUoW:
    async def __aenter__(self) -> _FakeUoW:
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
        return None

    async def rollback(self) -> None:
        return None


class FakeEmbeddings:
    def __init__(self, vectors: list[list[float]] | None = None) -> None:
        self.vectors = vectors if vectors is not None else [[0.1, 0.2, 0.3]]
        self.inputs: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.inputs.append(texts)
        return self.vectors


class FakeCatalogSearch:
    def __init__(self, hits: list[CatalogSearchHit] | None = None) -> None:
        self.hits = hits if hits is not None else []
        self.calls: list[dict[str, Any]] = []

    async def search(
        self,
        *,
        query_vector: list[float],
        filters: CatalogSearchFilters | None,
        limit: int,
    ) -> list[CatalogSearchHit]:
        self.calls.append(
            {
                "query_vector": query_vector,
                "filters": filters,
                "limit": limit,
            },
        )
        return self.hits[:limit]


class FakePriceItemSearchRepository:
    def __init__(self, items: list[PriceItem]) -> None:
        self.items = {item.id: item for item in items}
        self.keyword_hits: list[tuple[UUID, float, str]] = []
        self.keyword_calls: list[dict[str, Any]] = []
        self.hydrate_calls: list[dict[str, Any]] = []

    async def search_active_by_keywords(
        self,
        *,
        query: str,
        filters: SearchPriceItemsFilters,
        limit: int,
    ) -> list[tuple[UUID, float, str]]:
        self.keyword_calls.append(
            {
                "query": query,
                "filters": filters,
                "limit": limit,
            },
        )
        return self.keyword_hits[:limit]

    async def list_active_by_ids(
        self,
        item_ids: list[UUID],
        *,
        filters: SearchPriceItemsFilters,
    ) -> list[PriceItem]:
        self.hydrate_calls.append(
            {
                "item_ids": item_ids,
                "filters": filters,
            },
        )
        return [self.items[item_id] for item_id in item_ids if item_id in self.items]


class ImportedPriceItemSearchRepository:
    def __init__(self, items: list[PriceItem]) -> None:
        self.items = {item.id: item for item in items}
        self.keyword_calls: list[dict[str, Any]] = []
        self.hydrate_calls: list[dict[str, Any]] = []

    async def search_active_by_keywords(
        self,
        *,
        query: str,
        filters: SearchPriceItemsFilters,
        limit: int,
    ) -> list[tuple[UUID, float, MatchReasonCode]]:
        self.keyword_calls.append(
            {
                "query": query,
                "filters": filters,
                "limit": limit,
            },
        )
        keyword_query = build_keyword_query(query)
        hits: list[tuple[UUID, float, MatchReasonCode]] = []
        for item in self.items.values():
            if not price_item_matches_filters(item, filters):
                continue
            reason = keyword_reason_for_fields(
                price_item_keyword_fields(item),
                keyword_query,
            )
            if reason is None:
                continue
            hits.append((item.id, keyword_score(reason), reason))
            if len(hits) >= limit:
                break
        return hits

    async def list_active_by_ids(
        self,
        item_ids: list[UUID],
        *,
        filters: SearchPriceItemsFilters,
    ) -> list[PriceItem]:
        self.hydrate_calls.append(
            {
                "item_ids": item_ids,
                "filters": filters,
            },
        )
        return [
            self.items[item_id]
            for item_id in item_ids
            if item_id in self.items
            and price_item_matches_filters(self.items[item_id], filters)
        ]


def _item(
    *,
    name: str = "Аренда акустической системы",
    source_text: str | None = (
        "Аренда акустической системы 2 кВт для концертного зала, доставка отдельно"
    ),
    category: str | None = "Аренда",
    unit: str = "день",
    unit_price: Decimal = Decimal("15000.00"),
    supplier: str | None = "ООО НИКА",
    supplier_inn: str | None = "7701234567",
    supplier_city: str | None = "г. Москва",
    supplier_status: str | None = "Активен",
    has_vat: str | None = "Без НДС",
    external_id: str | None = "A-100",
) -> PriceItem:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return PriceItem(
        id=uuid4(),
        external_id=external_id,
        name=name,
        category=category,
        category_normalized=category.lower() if category else None,
        unit=unit,
        unit_normalized=unit.lower(),
        unit_price=unit_price,
        source_text=source_text,
        section="Оборудование",
        section_normalized="оборудование",
        supplier=supplier,
        has_vat=has_vat,
        vat_mode="without_vat",
        supplier_inn=supplier_inn,
        supplier_city=supplier_city,
        supplier_city_normalized="москва" if supplier_city else None,
        supplier_phone="+7",
        supplier_email="info@example.com",
        supplier_status=supplier_status,
        supplier_status_normalized=supplier_status.lower() if supplier_status else None,
        import_batch_id=uuid4(),
        source_file_id=uuid4(),
        source_import_row_id=uuid4(),
        row_fingerprint="fingerprint",
        is_active=True,
        superseded_at=None,
        embedding_text="Название: Аренда акустической системы",
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


def _use_case(
    *,
    items: list[PriceItem],
    semantic_hits: list[CatalogSearchHit] | None = None,
) -> tuple[
    SearchPriceItemsUseCase,
    FakePriceItemSearchRepository,
    FakeEmbeddings,
    FakeCatalogSearch,
]:
    repository = FakePriceItemSearchRepository(items)
    embeddings = FakeEmbeddings()
    vector_search = FakeCatalogSearch(semantic_hits)
    return (
        SearchPriceItemsUseCase(
            items=repository,
            embeddings=embeddings,
            vector_search=vector_search,
            catalog_query_prefix="search_query: ",
            catalog_embedding_template_version="prices_v1",
        ),
        repository,
        embeddings,
        vector_search,
    )


def _prices_csv_fixture_rows(external_ids: set[str]) -> bytes:
    with Path("test_files/prices.csv").open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        assert fieldnames is not None
        selected = [row for row in reader if row["id"] in external_ids]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(selected)
    return output.getvalue().encode()


async def _imported_prices_fixture_items() -> list[PriceItem]:
    imports = _FakeImportRepository()
    items = _FakeImportItemRepository()
    uow = _FakeUoW()
    uc = ImportPricesCsvUseCase(imports=imports, items=items, uow=uow)

    await uc.execute(
        filename="prices.csv",
        content=_prices_csv_fixture_rows(
            {"244", "325", "447", "467", "661", "897", "899"},
        ),
        source_path="test_files/prices.csv",
    )

    return items.items


def _imported_use_case(
    items: list[PriceItem],
) -> tuple[
    SearchPriceItemsUseCase,
    ImportedPriceItemSearchRepository,
    FakeCatalogSearch,
]:
    repository = ImportedPriceItemSearchRepository(items)
    vector_search = FakeCatalogSearch([])
    return (
        SearchPriceItemsUseCase(
            items=repository,
            embeddings=FakeEmbeddings(),
            vector_search=vector_search,
            catalog_query_prefix="search_query: ",
            catalog_embedding_template_version="prices_v1",
        ),
        repository,
        vector_search,
    )


@pytest.mark.asyncio
async def test_semantic_search_uses_query_prefix_hydrates_rows_and_preserves_ranking(
) -> None:
    first = _item(name="Аренда акустической системы")
    second = _item(name="Прокат сценического света")
    uc, repository, embeddings, vector_search = _use_case(
        items=[first, second],
        semantic_hits=[
            CatalogSearchHit(price_item_id=first.id, score=0.91, payload={}),
            CatalogSearchHit(price_item_id=second.id, score=0.73, payload={}),
        ],
    )

    result = await uc.execute(query="акустическая система", limit=10)

    assert embeddings.inputs == [["search_query: акустическая система"]]
    assert vector_search.calls == [
        {
            "query_vector": [0.1, 0.2, 0.3],
            "filters": CatalogSearchFilters(
                embedding_template_version="prices_v1",
            ),
            "limit": 10,
        },
    ]
    assert repository.hydrate_calls[0]["item_ids"] == [first.id, second.id]
    assert [item.id for item in result.items] == [first.id, second.id]
    assert result.items[0].score == 0.91
    assert result.items[0].match_reason.code == "semantic"


@pytest.mark.asyncio
async def test_applies_simple_filters_to_semantic_keyword_and_hydration() -> None:
    item = _item()
    filters = SearchPriceItemsFilters(
        supplier_city="г. Москва",
        category="Аренда",
        supplier_status="Активен",
        has_vat="Без НДС",
        unit_price=Decimal("15000.00"),
    )
    uc, repository, _embeddings, vector_search = _use_case(
        items=[item],
        semantic_hits=[CatalogSearchHit(price_item_id=item.id, score=0.8, payload={})],
    )

    await uc.execute(query="звук", filters=filters, limit=5)

    assert vector_search.calls[0]["filters"] == CatalogSearchFilters(
        category="Аренда",
        unit_price=15000.0,
        has_vat="Без НДС",
        supplier_city="г. Москва",
        supplier_status="Активен",
        embedding_template_version="prices_v1",
    )
    assert repository.keyword_calls == [
        {"query": "звук", "filters": filters, "limit": 5},
    ]
    assert repository.hydrate_calls == [
        {"item_ids": [item.id], "filters": filters},
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "reason_code"),
    [
        ("ООО НИКА", "keyword_supplier"),
        ("7701234567", "keyword_inn"),
        ("акустической системы", "keyword_name"),
        ("концертного зала", "keyword_source_text"),
        ("A-100", "keyword_external_id"),
    ],
)
async def test_keyword_fallback_returns_backend_generated_reason_codes(
    query: str,
    reason_code: str,
) -> None:
    item = _item()
    uc, repository, _embeddings, _vector_search = _use_case(items=[item])
    repository.keyword_hits = [(item.id, 0.45, reason_code)]

    result = await uc.execute(query=query, limit=10)

    assert [found.id for found in result.items] == [item.id]
    assert result.items[0].score == 0.45
    assert result.items[0].match_reason.code == reason_code
    assert result.items[0].match_reason.label != reason_code


@pytest.mark.asyncio
async def test_semantic_disabled_skips_embeddings_and_vector_search() -> None:
    item = _item(name="Радиомикрофон")
    repository = FakePriceItemSearchRepository([item])
    embeddings = FakeEmbeddings()
    vector_search = FakeCatalogSearch(
        [CatalogSearchHit(price_item_id=uuid4(), score=0.99, payload={})],
    )
    repository.keyword_hits = [(item.id, 0.72, "keyword_name")]
    uc = SearchPriceItemsUseCase(
        items=repository,
        embeddings=embeddings,
        vector_search=vector_search,
        catalog_query_prefix="search_query: ",
        catalog_embedding_template_version="prices_v1",
        semantic_search_enabled=False,
    )

    result = await uc.execute(query="радиомикрофон", limit=10)

    assert embeddings.inputs == []
    assert vector_search.calls == []
    assert repository.keyword_calls == [
        {
            "query": "радиомикрофон",
            "filters": SearchPriceItemsFilters(),
            "limit": 10,
        },
    ]
    assert repository.hydrate_calls == [
        {"item_ids": [item.id], "filters": SearchPriceItemsFilters()},
    ]
    assert [found.id for found in result.items] == [item.id]
    assert result.items[0].match_reason.code == "keyword_name"


@pytest.mark.asyncio
async def test_merges_semantic_and_keyword_results_without_duplicate_rows() -> None:
    semantic_item = _item(name="Аренда звука")
    keyword_item = _item(name="ООО НИКА доставка")
    uc, repository, _embeddings, _vector_search = _use_case(
        items=[semantic_item, keyword_item],
        semantic_hits=[
            CatalogSearchHit(price_item_id=semantic_item.id, score=0.9, payload={}),
        ],
    )
    repository.keyword_hits = [
        (semantic_item.id, 0.5, "keyword_name"),
        (keyword_item.id, 0.4, "keyword_supplier"),
    ]

    result = await uc.execute(query="ника звук", limit=10)

    assert [item.id for item in result.items] == [semantic_item.id, keyword_item.id]
    assert result.items[0].match_reason.code == "semantic"
    assert result.items[1].match_reason.code == "keyword_supplier"
    assert repository.hydrate_calls[0]["item_ids"] == [
        semantic_item.id,
        keyword_item.id,
    ]


@pytest.mark.asyncio
async def test_keyword_fallback_is_not_starved_by_full_semantic_limit() -> None:
    first_semantic = _item(name="Нерелевантная позиция 1", external_id="S-1")
    second_semantic = _item(name="Нерелевантная позиция 2", external_id="S-2")
    keyword_item = _item(name="Радиомикрофон", external_id="897")
    uc, repository, _embeddings, _vector_search = _use_case(
        items=[first_semantic, second_semantic, keyword_item],
        semantic_hits=[
            CatalogSearchHit(price_item_id=first_semantic.id, score=0.99, payload={}),
            CatalogSearchHit(price_item_id=second_semantic.id, score=0.98, payload={}),
        ],
    )
    repository.keyword_hits = [
        (keyword_item.id, 0.72, "keyword_external_id"),
    ]

    result = await uc.execute(query="897", limit=2)

    assert keyword_item.id in [found.id for found in result.items]
    assert len(result.items) == 2


@pytest.mark.asyncio
async def test_returns_source_text_snippet_and_full_available_flag() -> None:
    item = _item(
        source_text=(
            "Длинное описание услуги по аренде акустической системы для площадки. "
            "Включает стойки, коммутацию, базовую настройку и работу техника."
        ),
    )
    uc, _repository, _embeddings, _vector_search = _use_case(
        items=[item],
        semantic_hits=[CatalogSearchHit(price_item_id=item.id, score=0.9, payload={})],
    )

    result = await uc.execute(query="акустика", limit=10)

    found = result.items[0]
    assert found.source_text_snippet is not None
    assert found.source_text_snippet.startswith("Длинное описание услуги")
    assert len(found.source_text_snippet) < len(item.source_text or "")
    assert found.source_text_full_available is True
    assert found.match_reason.label == "Семантическое совпадение с запросом"


@pytest.mark.asyncio
async def test_empty_semantic_and_keyword_results_return_empty_items() -> None:
    uc, repository, _embeddings, _vector_search = _use_case(items=[])
    repository.keyword_hits = []

    result = await uc.execute(query="несуществующая позиция", limit=10)

    assert result.items == []
    assert repository.hydrate_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_external_id"),
    [
        ("ООО НИКА", "897"),
        ("7726476100", "897"),
        ("радиомикрофон", "244"),
        ("фермы", "325"),
        ("Екат", "244"),
        ("Без НДС", "897"),
        ("897", "897"),
        ("1.1.2. Оператор ПТС", "899"),
        ("ПТС", "447"),
        ("Активен", "897"),
        ("Оборудование", "244"),
    ],
)
async def test_keyword_fallback_finds_imported_prices_csv_fields_with_weak_vectors(
    query: str,
    expected_external_id: str,
) -> None:
    imported_items = await _imported_prices_fixture_items()
    item_by_id = {item.id: item for item in imported_items}
    uc, repository, vector_search = _imported_use_case(imported_items)

    result = await uc.execute(query=query, limit=20)

    assert vector_search.calls[0]["query_vector"] == [0.1, 0.2, 0.3]
    assert repository.keyword_calls[0]["query"] == query
    assert any(
        item_by_id[found.id].external_id == expected_external_id
        for found in result.items
    )


@pytest.mark.asyncio
async def test_semantic_disabled_finds_imported_prices_csv_row_by_keyword() -> None:
    imported_items = await _imported_prices_fixture_items()
    item_by_id = {item.id: item for item in imported_items}
    repository = ImportedPriceItemSearchRepository(imported_items)
    embeddings = FakeEmbeddings()
    vector_search = FakeCatalogSearch([])
    uc = SearchPriceItemsUseCase(
        items=repository,
        embeddings=embeddings,
        vector_search=vector_search,
        catalog_query_prefix="search_query: ",
        catalog_embedding_template_version="prices_v1",
        semantic_search_enabled=False,
    )

    result = await uc.execute(query="897", limit=20)

    assert embeddings.inputs == []
    assert vector_search.calls == []
    assert repository.keyword_calls[0]["query"] == "897"
    assert any(item_by_id[found.id].external_id == "897" for found in result.items)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "радиомикрофон Екатеринбург",
        "найди радиомикрофон в Екатеринбурге",
    ],
)
async def test_semantic_disabled_retries_clean_query_for_imported_natural_query(
    query: str,
) -> None:
    imported_items = await _imported_prices_fixture_items()
    item_by_id = {item.id: item for item in imported_items}
    repository = ImportedPriceItemSearchRepository(imported_items)
    embeddings = FakeEmbeddings()
    vector_search = FakeCatalogSearch([])
    uc = SearchPriceItemsUseCase(
        items=repository,
        embeddings=embeddings,
        vector_search=vector_search,
        catalog_query_prefix="search_query: ",
        catalog_embedding_template_version="prices_v1",
        semantic_search_enabled=False,
    )

    result = await uc.execute(query=query, limit=20)

    assert embeddings.inputs == []
    assert vector_search.calls == []
    assert [call["query"] for call in repository.keyword_calls] == [
        query,
        "радиомикрофон",
    ]
    assert all(
        call["filters"].supplier_city_normalized == "екатеринбург"
        for call in repository.keyword_calls
    )
    assert any(item_by_id[found.id].external_id == "244" for found in result.items)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_filters"),
    [
        ("Екат", {"supplier_city_normalized": "екатеринбург"}),
        ("Без НДС", {"has_vat": "Без НДС", "vat_mode": "without_vat"}),
        ("Активен", {"supplier_status_normalized": "активен"}),
    ],
)
async def test_search_infers_simple_filters_from_catalog_keyword_phrases(
    query: str,
    expected_filters: dict[str, str],
) -> None:
    imported_items = await _imported_prices_fixture_items()
    uc, repository, vector_search = _imported_use_case(imported_items)

    await uc.execute(query=query, limit=20)

    semantic_filters = vector_search.calls[0]["filters"]
    keyword_filters = repository.keyword_calls[0]["filters"]
    for key, value in expected_filters.items():
        assert getattr(semantic_filters, key) == value
        assert getattr(keyword_filters, key) == value
