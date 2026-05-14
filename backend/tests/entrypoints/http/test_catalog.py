from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from app.entrypoints.http.dependencies import (
    get_get_price_item_uc,
    get_import_prices_csv_uc,
    get_index_price_items_uc,
    get_list_price_items_uc,
    get_search_price_items_uc,
)
from app.features.catalog.dto import FoundPriceItem, MatchReason, SearchPriceItemsResult
from app.features.catalog.entities.price_item import PriceItem, PriceItemSourceRef
from app.features.catalog.use_cases.import_prices_csv import PriceImportSummary
from app.features.catalog.use_cases.index_price_items import IndexPriceItemsResult
from app.features.catalog.use_cases.list_price_items import PriceItemList
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def _item() -> PriceItem:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return PriceItem(
        id=uuid4(),
        external_id="10",
        name="Аренда света",
        category="Аренда",
        category_normalized="аренда",
        unit="шт.",
        unit_normalized="шт",
        unit_price=Decimal("1200.00"),
        source_text="Описание",
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
        is_active=True,
        superseded_at=None,
        embedding_text="Название: Аренда света",
        embedding_model="nomic-embed-text-v1.5",
        embedding_template_version="prices_v1",
        catalog_index_status="pending",
        embedding_error=None,
        indexing_error=None,
        indexed_at=None,
        legacy_embedding_present=False,
        legacy_embedding_dim=None,
        created_at=now,
        updated_at=now,
    )


async def test_import_catalog_returns_summary(app: FastAPI) -> None:
    import_id = uuid4()
    source_file_id = uuid4()
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = PriceImportSummary(
        id=import_id,
        source_file_id=source_file_id,
        filename="prices.csv",
        status="IMPORTED",
        row_count=1,
        valid_row_count=1,
        invalid_row_count=0,
        embedding_template_version="prices_v1",
        embedding_model="nomic-embed-text-v1.5",
        duplicate_file=False,
    )
    app.dependency_overrides[get_import_prices_csv_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/catalog/imports",
            files={"file": ("prices.csv", b"id,name\n1,test\n", "text/csv")},
        )

    assert resp.status_code == 201
    assert resp.json()["id"] == str(import_id)
    assert resp.json()["source_file_id"] == str(source_file_id)
    fake_uc.execute.assert_awaited_once()


async def test_import_catalog_indexed_imports_csv_and_indexes_items(
    app: FastAPI,
) -> None:
    import_id = uuid4()
    source_file_id = uuid4()
    import_uc = AsyncMock()
    import_uc.execute.return_value = PriceImportSummary(
        id=import_id,
        source_file_id=source_file_id,
        filename="prices.csv",
        status="IMPORTED",
        row_count=3,
        valid_row_count=2,
        invalid_row_count=1,
        embedding_template_version="prices_v1",
        embedding_model="nomic-embed-text-v1.5",
        duplicate_file=False,
    )
    index_uc = AsyncMock()
    index_uc.execute.return_value = IndexPriceItemsResult(
        total=2,
        indexed=1,
        embedding_failed=0,
        indexing_failed=1,
        skipped=0,
    )
    app.dependency_overrides[get_import_prices_csv_uc] = lambda: import_uc
    app.dependency_overrides[get_index_price_items_uc] = lambda: index_uc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/catalog/imports/indexed?index_limit=25",
            files={"file": ("prices.csv", b"id,name\n1,test\n", "text/csv")},
        )

    assert resp.status_code == 201
    assert resp.json() == {
        "import": {
            "id": str(import_id),
            "source_file_id": str(source_file_id),
            "filename": "prices.csv",
            "status": "IMPORTED",
            "row_count": 3,
            "valid_row_count": 2,
            "invalid_row_count": 1,
            "embedding_template_version": "prices_v1",
            "embedding_model": "nomic-embed-text-v1.5",
            "duplicate_file": False,
        },
        "indexing": {
            "total": 2,
            "indexed": 1,
            "embedding_failed": 0,
            "indexing_failed": 1,
            "skipped": 0,
        },
    }
    import_uc.execute.assert_awaited_once_with(
        filename="prices.csv",
        content=b"id,name\n1,test\n",
    )
    index_uc.execute.assert_awaited_once_with(limit=25)


async def test_list_catalog_items_returns_items_and_total(app: FastAPI) -> None:
    item = _item()
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = PriceItemList(items=[item], total=1)
    app.dependency_overrides[get_list_price_items_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/catalog/items?limit=20&offset=0")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert UUID(body["items"][0]["id"]) == item.id
    assert body["items"][0]["unit_price"] == "1200.00"


async def test_get_catalog_item_returns_detail_and_sources(app: FastAPI) -> None:
    item = _item()
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = (
        item,
        [
            PriceItemSourceRef(
                source_kind="csv_import",
                import_batch_id=item.import_batch_id,
                source_file_id=item.source_file_id,
                price_import_row_id=item.source_import_row_id,
                row_number=42,
                source_text="Описание",
            ),
        ],
    )
    app.dependency_overrides[get_get_price_item_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/catalog/items/{item.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["item"]["id"] == str(item.id)
    assert body["item"]["embedding_text"] == "Название: Аренда света"
    assert body["sources"][0]["row_number"] == 42


async def test_search_catalog_items_returns_found_item_cards(app: FastAPI) -> None:
    item = _item()
    fake_uc = AsyncMock()
    fake_uc.execute.return_value = SearchPriceItemsResult(
        items=[
            FoundPriceItem(
                id=item.id,
                score=0.82,
                name=item.name,
                category=item.category,
                unit=item.unit,
                unit_price=item.unit_price,
                supplier=item.supplier,
                supplier_city=item.supplier_city,
                source_text_snippet="Описание",
                source_text_full_available=True,
                match_reason=MatchReason(
                    code="semantic",
                    label="Семантическое совпадение с запросом",
                ),
            ),
        ],
    )
    app.dependency_overrides[get_search_price_items_uc] = lambda: fake_uc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/catalog/search",
            json={
                "query": "аренда света",
                "limit": 10,
                "filters": {
                    "supplier_city": "г. Москва",
                    "category": "Аренда",
                    "supplier_status": "Активен",
                    "has_vat": "Без НДС",
                    "unit_price": "1200.00",
                },
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == [
        {
            "id": str(item.id),
            "score": 0.82,
            "name": "Аренда света",
            "category": "Аренда",
            "unit": "шт.",
            "unit_price": "1200.00",
            "supplier": "ООО Ромашка",
            "supplier_city": "г. Москва",
            "source_text_snippet": "Описание",
            "source_text_full_available": True,
            "match_reason": {
                "code": "semantic",
                "label": "Семантическое совпадение с запросом",
            },
        },
    ]
    call = fake_uc.execute.await_args.kwargs
    assert call["query"] == "аренда света"
    assert call["limit"] == 10
    assert call["filters"].supplier_city == "г. Москва"
    assert call["filters"].category == "Аренда"
    assert call["filters"].unit_price == Decimal("1200.00")
