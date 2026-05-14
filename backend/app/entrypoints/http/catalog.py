from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.entrypoints.http.dependencies import (
    CatalogImportJobFetcher,
    get_catalog_import_job_fetcher,
    get_get_catalog_import_job_uc,
    get_get_price_item_uc,
    get_import_prices_csv_uc,
    get_index_price_items_uc,
    get_list_price_items_uc,
    get_search_price_items_uc,
    get_start_catalog_import_job_uc,
)
from app.entrypoints.http.schemas.catalog import (
    CatalogImportIndexedOut,
    CatalogImportJobOut,
    CatalogSearchRequestIn,
    CatalogSearchResultOut,
    PriceImportSummaryOut,
    PriceItemDetailItemOut,
    PriceItemDetailOut,
    PriceItemListOut,
    PriceItemOut,
    PriceItemSourceOut,
)
from app.features.catalog.entities.import_job import CatalogImportJob
from app.features.catalog.ports import CatalogImportJobNotFound, PriceItemNotFound
from app.features.catalog.use_cases.get_import_job import GetCatalogImportJobUseCase
from app.features.catalog.use_cases.get_price_item import GetPriceItemUseCase
from app.features.catalog.use_cases.import_prices_csv import ImportPricesCsvUseCase
from app.features.catalog.use_cases.index_price_items import IndexPriceItemsUseCase
from app.features.catalog.use_cases.list_price_items import ListPriceItemsUseCase
from app.features.catalog.use_cases.search_price_items import SearchPriceItemsUseCase
from app.features.catalog.use_cases.start_import_job import StartCatalogImportJobUseCase

router = APIRouter(prefix="/catalog", tags=["catalog"])
logger = logging.getLogger(__name__)

_JOB_TERMINAL = frozenset({"COMPLETED", "FAILED"})
type _JobRepo = Callable[[UUID], Coroutine[Any, Any, CatalogImportJob]]


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


@router.post(
    "/imports/indexed",
    status_code=201,
    response_model=CatalogImportIndexedOut,
    operation_id="importAndIndexCatalogCsv",
    summary="Import and index catalog CSV",
    description=(
        "Imports a prices.csv-compatible file into price_items and immediately "
        "indexes active catalog items into price_items_search_v1 for service "
        "testing."
    ),
)
async def import_and_index_catalog_csv(
    file: UploadFile,
    import_uc: Annotated[ImportPricesCsvUseCase, Depends(get_import_prices_csv_uc)],
    index_uc: Annotated[IndexPriceItemsUseCase, Depends(get_index_price_items_uc)],
    index_limit: int = 1000,
) -> CatalogImportIndexedOut:
    content = await file.read()
    import_summary = await import_uc.execute(
        filename=file.filename or "prices.csv",
        content=content,
    )
    indexing_result = await index_uc.execute(
        limit=index_limit,
        import_batch_id=import_summary.id,
    )
    return CatalogImportIndexedOut.from_domain(
        import_summary=import_summary,
        indexing_result=indexing_result,
    )


@router.post(
    "/import-jobs",
    status_code=202,
    response_model=CatalogImportJobOut,
    operation_id="startCatalogImportJob",
    summary="Start catalog import job",
    description=(
        "Stores the uploaded catalog CSV on disk, creates a DB-backed progress "
        "job and enqueues async import plus indexing."
    ),
)
async def start_catalog_import_job(
    file: UploadFile,
    uc: Annotated[
        StartCatalogImportJobUseCase,
        Depends(get_start_catalog_import_job_uc),
    ],
) -> CatalogImportJobOut:
    job = await uc.execute(file=file.file, filename=file.filename or "prices.csv")
    return CatalogImportJobOut.from_domain(job)


@router.get(
    "/import-jobs/{id}",
    response_model=CatalogImportJobOut,
    operation_id="getCatalogImportJob",
    summary="Get catalog import job",
)
async def get_catalog_import_job(
    id: UUID,
    uc: Annotated[
        GetCatalogImportJobUseCase,
        Depends(get_get_catalog_import_job_uc),
    ],
) -> CatalogImportJobOut:
    try:
        job = await uc.execute(id)
    except CatalogImportJobNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Catalog import job not found",
        ) from exc
    return CatalogImportJobOut.from_domain(job)


async def _job_status_stream(
    job_id: UUID,
    repo: _JobRepo,
) -> AsyncIterator[str]:
    last_payload: dict[str, Any] | None = None

    while True:
        try:
            job = await repo(job_id)
        except CatalogImportJobNotFound:
            raise
        except Exception:
            logger.exception("Catalog import job SSE poll failed for %s", job_id)
            await asyncio.sleep(1)
            continue

        payload = CatalogImportJobOut.from_domain(job).model_dump(mode="json")
        if payload != last_payload:
            last_payload = payload
            yield f"data: {json.dumps(payload)}\n\n"

        if job.status in _JOB_TERMINAL:
            break

        await asyncio.sleep(1)


@router.get(
    "/import-jobs/{id}/stream",
    response_class=StreamingResponse,
    operation_id="streamCatalogImportJob",
    summary="Stream catalog import job progress",
)
async def stream_catalog_import_job(
    id: UUID,
    fetch_job: Annotated[
        CatalogImportJobFetcher,
        Depends(get_catalog_import_job_fetcher),
    ],
) -> StreamingResponse:
    try:
        await fetch_job(id)
    except CatalogImportJobNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Catalog import job not found",
        ) from exc

    return StreamingResponse(
        _job_status_stream(id, fetch_job),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
        indexed_total=result.indexed_total,
    )


@router.post(
    "/search",
    response_model=CatalogSearchResultOut,
    operation_id="searchCatalogItems",
    summary="Search catalog items",
    description=(
        "Searches price_items semantically in price_items_search_v1, supplements "
        "with minimal Postgres keyword fallback, hydrates rows from Postgres and "
        "returns checkable catalog item cards."
    ),
)
async def search_catalog_items(
    request: CatalogSearchRequestIn,
    uc: Annotated[SearchPriceItemsUseCase, Depends(get_search_price_items_uc)],
) -> CatalogSearchResultOut:
    result = await uc.execute(
        query=request.query,
        filters=request.filters_to_domain(),
        limit=request.limit,
    )
    return CatalogSearchResultOut.from_domain(result)


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
