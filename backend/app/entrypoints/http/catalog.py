from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.entrypoints.http.dependencies import (
    get_get_price_item_uc,
    get_import_prices_csv_uc,
    get_list_price_items_uc,
)
from app.entrypoints.http.schemas.catalog import (
    PriceImportSummaryOut,
    PriceItemDetailItemOut,
    PriceItemDetailOut,
    PriceItemListOut,
    PriceItemOut,
    PriceItemSourceOut,
)
from app.features.catalog.ports import PriceItemNotFound
from app.features.catalog.use_cases.get_price_item import GetPriceItemUseCase
from app.features.catalog.use_cases.import_prices_csv import ImportPricesCsvUseCase
from app.features.catalog.use_cases.list_price_items import ListPriceItemsUseCase

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.post(
    "/imports",
    status_code=201,
    response_model=PriceImportSummaryOut,
    operation_id="importCatalogCsv",
    summary="Import catalog CSV",
    description=(
        "Imports a prices.csv-compatible file as raw import rows plus normalized "
        "active price_items. Legacy CSV embeddings are preserved only as audit "
        "metadata."
    ),
)
async def import_catalog_csv(
    file: UploadFile,
    uc: Annotated[ImportPricesCsvUseCase, Depends(get_import_prices_csv_uc)],
) -> PriceImportSummaryOut:
    content = await file.read()
    summary = await uc.execute(
        filename=file.filename or "prices.csv",
        content=content,
    )
    return PriceImportSummaryOut.from_domain(summary)


@router.get(
    "/items",
    response_model=PriceItemListOut,
    operation_id="listCatalogItems",
    summary="List active catalog items",
    description="Returns active price_items for catalog administration and hydration.",
)
async def list_catalog_items(
    uc: Annotated[ListPriceItemsUseCase, Depends(get_list_price_items_uc)],
    limit: int = 50,
    offset: int = 0,
) -> PriceItemListOut:
    result = await uc.execute(limit=limit, offset=offset)
    return PriceItemListOut(
        items=[PriceItemOut.from_domain(item) for item in result.items],
        total=result.total,
    )


@router.get(
    "/items/{id}",
    response_model=PriceItemDetailOut,
    operation_id="getCatalogItem",
    summary="Get catalog item detail",
    description="Returns a full price_item row with CSV import provenance.",
)
async def get_catalog_item(
    id: UUID,
    uc: Annotated[GetPriceItemUseCase, Depends(get_get_price_item_uc)],
) -> PriceItemDetailOut:
    try:
        item, sources = await uc.execute(id)
    except PriceItemNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Catalog item not found",
        ) from exc
    return PriceItemDetailOut(
        item=PriceItemDetailItemOut.from_domain(item),
        sources=[PriceItemSourceOut.from_domain(source) for source in sources],
    )


__all__ = ["router"]
