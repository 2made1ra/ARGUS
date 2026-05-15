from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.sqlalchemy.models import PriceImportRow as PriceImportRowRow
from app.adapters.sqlalchemy.models import PriceItem as PriceItemRow
from app.adapters.sqlalchemy.models import PriceItemSource as PriceItemSourceRow
from app.features.catalog.domain.keyword_search import (
    CatalogKeywordFields,
    KeywordQuery,
    build_keyword_query,
    keyword_reason_for_fields,
    keyword_score,
)
from app.features.catalog.dto import MatchReasonCode, SearchPriceItemsFilters
from app.features.catalog.entities.price_item import (
    PriceItem,
    PriceItemDetail,
    PriceItemList,
    PriceItemSource,
    PriceItemSourceRef,
)
from app.features.catalog.ports import (
    PriceItemDuplicateFingerprint,
    PriceItemNotFound,
)


class SqlAlchemyPriceItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: PriceItem) -> None:
        statement = insert(PriceItemRow).values(**_item_values(item))
        try:
            async with self._session.begin_nested():
                await self._session.execute(statement)
        except IntegrityError as exc:
            if _is_active_fingerprint_integrity_error(exc):
                raise PriceItemDuplicateFingerprint(item.row_fingerprint) from exc
            raise

    async def add_source(self, source: PriceItemSource) -> None:
        statement = insert(PriceItemSourceRow).values(
            id=source.id,
            price_item_id=source.price_item_id,
            source_kind=source.source_kind,
            import_batch_id=source.import_batch_id,
            source_file_id=source.source_file_id,
            price_import_row_id=source.price_import_row_id,
            source_text=source.source_text,
            created_at=source.created_at,
        )
        await self._session.execute(statement)

    async def find_active_by_row_fingerprint(
        self,
        row_fingerprint: str,
    ) -> PriceItem | None:
        statement = select(PriceItemRow).where(
            PriceItemRow.row_fingerprint == row_fingerprint,
            PriceItemRow.is_active.is_(True),
        )
        row = await self._session.scalar(statement)
        return _item_to_entity(row) if row is not None else None

    async def list_active(self, *, limit: int, offset: int) -> PriceItemList:
        statement = (
            select(PriceItemRow)
            .where(PriceItemRow.is_active.is_(True))
            .order_by(PriceItemRow.created_at.desc(), PriceItemRow.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = await self._session.scalars(statement)
        items = [_item_to_entity(row) for row in rows]

        count_statement = (
            select(func.count())
            .select_from(PriceItemRow)
            .where(PriceItemRow.is_active.is_(True))
        )
        total_value = await self._session.scalar(count_statement)
        total = total_value if isinstance(total_value, int) else len(items)

        indexed_count_statement = (
            select(func.count())
            .select_from(PriceItemRow)
            .where(
                PriceItemRow.is_active.is_(True),
                PriceItemRow.catalog_index_status == "indexed",
            )
        )
        indexed_total_value = await self._session.scalar(indexed_count_statement)
        indexed_total = (
            indexed_total_value
            if isinstance(indexed_total_value, int)
            else sum(1 for item in items if item.catalog_index_status == "indexed")
        )
        return PriceItemList(
            items=items,
            total=total,
            indexed_total=indexed_total,
        )

    async def list_active_by_ids(
        self,
        item_ids: list[UUID],
        *,
        filters: SearchPriceItemsFilters,
    ) -> list[PriceItem]:
        if not item_ids:
            return []

        statement = select(PriceItemRow).where(
            PriceItemRow.id.in_(item_ids),
            PriceItemRow.is_active.is_(True),
            *_search_filter_conditions(filters),
        )
        rows = await self._session.scalars(statement)
        return [_item_to_entity(row) for row in rows]

    async def search_active_by_keywords(
        self,
        *,
        query: str,
        filters: SearchPriceItemsFilters,
        limit: int,
    ) -> list[tuple[UUID, float, MatchReasonCode]]:
        query = query.strip()
        if not query or limit < 1:
            return []

        keyword_query = build_keyword_query(query)
        keyword_conditions = _keyword_conditions(keyword_query)
        if not keyword_conditions:
            return []

        statement = (
            select(PriceItemRow)
            .where(
                PriceItemRow.is_active.is_(True),
                *_search_filter_conditions(filters),
                or_(*keyword_conditions),
            )
            .order_by(PriceItemRow.created_at.desc(), PriceItemRow.id.desc())
            .limit(limit * 5)
        )
        rows = await self._session.scalars(statement)

        hits: list[tuple[UUID, float, MatchReasonCode]] = []
        seen: set[UUID] = set()
        for row in rows:
            reason = keyword_reason_for_fields(
                _keyword_fields_from_row(row),
                keyword_query,
            )
            if reason is None or row.id in seen:
                continue
            hits.append((row.id, keyword_score(reason), reason))
            seen.add(row.id)
            if len(hits) >= limit:
                break
        return hits

    async def list_active_for_indexing(
        self,
        *,
        limit: int | None,
        import_batch_id: UUID | None = None,
    ) -> list[PriceItem]:
        conditions: list[object] = [
            PriceItemRow.is_active.is_(True),
            PriceItemRow.catalog_index_status != "indexed",
        ]
        if import_batch_id is not None:
            conditions.append(PriceItemRow.import_batch_id == import_batch_id)

        statement = (
            select(PriceItemRow)
            .where(*conditions)
            .order_by(PriceItemRow.created_at.asc(), PriceItemRow.id.asc())
        )
        if limit is not None:
            statement = statement.limit(limit)
        rows = await self._session.scalars(statement)
        return [_item_to_entity(row) for row in rows]

    async def get_legacy_embedding(self, item_id: UUID) -> list[float] | None:
        statement = (
            select(PriceImportRowRow.raw)
            .select_from(PriceItemRow)
            .join(
                PriceImportRowRow,
                PriceItemRow.source_import_row_id == PriceImportRowRow.id,
            )
            .where(PriceItemRow.id == item_id)
        )
        raw = await self._session.scalar(statement)
        if not isinstance(raw, dict):
            return None
        return _legacy_embedding_from_raw(raw)

    async def list_active_for_category_enrichment(
        self,
        *,
        limit: int,
    ) -> list[PriceItem]:
        statement = (
            select(PriceItemRow)
            .where(
                PriceItemRow.is_active.is_(True),
                PriceItemRow.category_enrichment_status == "pending",
            )
            .order_by(PriceItemRow.created_at.asc(), PriceItemRow.id.asc())
            .limit(limit)
        )
        rows = await self._session.scalars(statement)
        return [_item_to_entity(row) for row in rows]

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
        statement = (
            update(PriceItemRow)
            .where(PriceItemRow.id == item_id)
            .values(
                service_category=service_category,
                service_category_confidence=confidence,
                service_category_source="llm",
                service_category_reason=reason,
                category_enrichment_status="enriched",
                category_enrichment_error=None,
                category_enriched_at=enriched_at,
                category_enrichment_model=model,
                category_enrichment_prompt_version=prompt_version,
                embedding_text=embedding_text,
                updated_at=enriched_at,
            )
        )
        await self._session.execute(statement)

    async def mark_category_enrichment_failed(
        self,
        item_id: UUID,
        *,
        error: str,
        model: str,
        prompt_version: str,
    ) -> None:
        now = datetime.now(UTC)
        statement = (
            update(PriceItemRow)
            .where(PriceItemRow.id == item_id)
            .values(
                category_enrichment_status="failed",
                category_enrichment_error=error,
                category_enrichment_model=model,
                category_enrichment_prompt_version=prompt_version,
                updated_at=now,
            )
        )
        await self._session.execute(statement)

    async def mark_indexed(
        self,
        item_id: UUID,
        *,
        embedding_model: str,
        embedding_template_version: str,
        indexed_at: datetime,
    ) -> None:
        statement = (
            update(PriceItemRow)
            .where(PriceItemRow.id == item_id)
            .values(
                embedding_model=embedding_model,
                embedding_template_version=embedding_template_version,
                catalog_index_status="indexed",
                embedding_error=None,
                indexing_error=None,
                indexed_at=indexed_at,
                updated_at=indexed_at,
            )
        )
        await self._session.execute(statement)

    async def mark_embedding_failed(self, item_id: UUID, *, error: str) -> None:
        statement = (
            update(PriceItemRow)
            .where(PriceItemRow.id == item_id)
            .values(
                catalog_index_status="embedding_failed",
                embedding_error=error,
                indexing_error=None,
                indexed_at=None,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(statement)

    async def mark_indexing_failed(self, item_id: UUID, *, error: str) -> None:
        statement = (
            update(PriceItemRow)
            .where(PriceItemRow.id == item_id)
            .values(
                catalog_index_status="indexing_failed",
                embedding_error=None,
                indexing_error=error,
                indexed_at=None,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(statement)

    async def get_with_sources(self, item_id: UUID) -> PriceItemDetail:
        item_statement = select(PriceItemRow).where(PriceItemRow.id == item_id)
        item_row = await self._session.scalar(item_statement)
        if item_row is None:
            raise PriceItemNotFound(item_id)

        sources_statement = (
            select(PriceItemSourceRow, PriceImportRowRow.row_number)
            .outerjoin(
                PriceImportRowRow,
                PriceItemSourceRow.price_import_row_id == PriceImportRowRow.id,
            )
            .where(PriceItemSourceRow.price_item_id == item_id)
            .order_by(PriceItemSourceRow.created_at.asc(), PriceItemSourceRow.id.asc())
        )
        result = await self._session.execute(sources_statement)
        sources = [
            PriceItemSourceRef(
                source_kind=source_row.source_kind,
                import_batch_id=source_row.import_batch_id,
                source_file_id=source_row.source_file_id,
                price_import_row_id=source_row.price_import_row_id,
                row_number=row_number,
                source_text=source_row.source_text,
            )
            for source_row, row_number in result
        ]
        return PriceItemDetail(item=_item_to_entity(item_row), sources=sources)


def _item_values(item: PriceItem) -> dict[str, object]:
    return {
        "id": item.id,
        "external_id": item.external_id,
        "name": item.name,
        "category": item.category,
        "category_normalized": item.category_normalized,
        "service_category": item.service_category,
        "service_category_confidence": item.service_category_confidence,
        "service_category_source": item.service_category_source,
        "service_category_reason": item.service_category_reason,
        "category_enrichment_status": item.category_enrichment_status,
        "category_enrichment_error": item.category_enrichment_error,
        "category_enriched_at": item.category_enriched_at,
        "category_enrichment_model": item.category_enrichment_model,
        "category_enrichment_prompt_version": item.category_enrichment_prompt_version,
        "unit": item.unit,
        "unit_normalized": item.unit_normalized,
        "unit_price": item.unit_price,
        "source_text": item.source_text,
        "section": item.section,
        "section_normalized": item.section_normalized,
        "supplier": item.supplier,
        "has_vat": item.has_vat,
        "vat_mode": item.vat_mode,
        "supplier_inn": item.supplier_inn,
        "supplier_city": item.supplier_city,
        "supplier_city_normalized": item.supplier_city_normalized,
        "supplier_phone": item.supplier_phone,
        "supplier_email": item.supplier_email,
        "supplier_status": item.supplier_status,
        "supplier_status_normalized": item.supplier_status_normalized,
        "import_batch_id": item.import_batch_id,
        "source_file_id": item.source_file_id,
        "source_import_row_id": item.source_import_row_id,
        "row_fingerprint": item.row_fingerprint,
        "is_active": item.is_active,
        "superseded_at": item.superseded_at,
        "embedding_text": item.embedding_text,
        "embedding_model": item.embedding_model,
        "embedding_template_version": item.embedding_template_version,
        "catalog_index_status": item.catalog_index_status,
        "embedding_error": item.embedding_error,
        "indexing_error": item.indexing_error,
        "indexed_at": item.indexed_at,
        "legacy_embedding_present": item.legacy_embedding_present,
        "legacy_embedding_dim": item.legacy_embedding_dim,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _item_to_entity(row: PriceItemRow) -> PriceItem:
    return PriceItem(
        id=row.id,
        external_id=row.external_id,
        name=row.name,
        category=row.category,
        category_normalized=row.category_normalized,
        service_category=row.service_category,
        service_category_confidence=row.service_category_confidence,
        service_category_source=row.service_category_source,
        service_category_reason=row.service_category_reason,
        category_enrichment_status=row.category_enrichment_status,  # type: ignore[arg-type]
        category_enrichment_error=row.category_enrichment_error,
        category_enriched_at=row.category_enriched_at,
        category_enrichment_model=row.category_enrichment_model,
        category_enrichment_prompt_version=row.category_enrichment_prompt_version,
        unit=row.unit,
        unit_normalized=row.unit_normalized,
        unit_price=row.unit_price,
        source_text=row.source_text,
        section=row.section,
        section_normalized=row.section_normalized,
        supplier=row.supplier,
        has_vat=row.has_vat,
        vat_mode=row.vat_mode,
        supplier_inn=row.supplier_inn,
        supplier_city=row.supplier_city,
        supplier_city_normalized=row.supplier_city_normalized,
        supplier_phone=row.supplier_phone,
        supplier_email=row.supplier_email,
        supplier_status=row.supplier_status,
        supplier_status_normalized=row.supplier_status_normalized,
        import_batch_id=row.import_batch_id,
        source_file_id=row.source_file_id,
        source_import_row_id=row.source_import_row_id,
        row_fingerprint=row.row_fingerprint,
        is_active=row.is_active,
        superseded_at=row.superseded_at,
        embedding_text=row.embedding_text,
        embedding_model=row.embedding_model,
        embedding_template_version=row.embedding_template_version,
        catalog_index_status=row.catalog_index_status,  # type: ignore[arg-type]
        embedding_error=row.embedding_error,
        indexing_error=row.indexing_error,
        indexed_at=row.indexed_at,
        legacy_embedding_present=row.legacy_embedding_present,
        legacy_embedding_dim=row.legacy_embedding_dim,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _legacy_embedding_from_raw(raw: dict[str, object]) -> list[float] | None:
    value = raw.get("embedding")
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("Legacy CSV embedding is not valid JSON") from exc

    if not isinstance(parsed, list):
        raise ValueError("Legacy CSV embedding must be a JSON array")

    vector: list[float] = []
    for element in parsed:
        if isinstance(element, bool) or not isinstance(element, int | float):
            raise ValueError("Legacy CSV embedding contains a non-numeric value")
        vector.append(float(element))
    return vector


def _is_active_fingerprint_integrity_error(exc: IntegrityError) -> bool:
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name == "ix_price_items_row_fingerprint_active":
        return True
    return "ix_price_items_row_fingerprint_active" in str(exc.orig)


def _search_filter_conditions(filters: SearchPriceItemsFilters) -> list[object]:
    conditions: list[object] = []
    if filters.supplier_city is not None:
        conditions.append(PriceItemRow.supplier_city == filters.supplier_city)
    if filters.supplier_city_normalized is not None:
        conditions.append(
            PriceItemRow.supplier_city_normalized == filters.supplier_city_normalized,
        )
    if filters.category is not None:
        conditions.append(PriceItemRow.category == filters.category)
    if filters.category_normalized is not None:
        conditions.append(
            PriceItemRow.category_normalized == filters.category_normalized,
        )
    if filters.service_category is not None:
        conditions.append(PriceItemRow.service_category == filters.service_category)
    if filters.section is not None:
        conditions.append(PriceItemRow.section == filters.section)
    if filters.section_normalized is not None:
        conditions.append(
            PriceItemRow.section_normalized == filters.section_normalized,
        )
    if filters.supplier_status is not None:
        conditions.append(PriceItemRow.supplier_status == filters.supplier_status)
    if filters.supplier_status_normalized is not None:
        conditions.append(
            PriceItemRow.supplier_status_normalized
            == filters.supplier_status_normalized,
        )
    if filters.has_vat is not None:
        conditions.append(PriceItemRow.has_vat == filters.has_vat)
    if filters.vat_mode is not None:
        conditions.append(PriceItemRow.vat_mode == filters.vat_mode)
    if filters.unit_price is not None:
        conditions.append(PriceItemRow.unit_price == filters.unit_price)
    if filters.unit_price_min is not None:
        conditions.append(PriceItemRow.unit_price >= filters.unit_price_min)
    if filters.unit_price_max is not None:
        conditions.append(PriceItemRow.unit_price <= filters.unit_price_max)
    return conditions


def _keyword_conditions(keyword_query: KeywordQuery) -> list[object]:
    conditions: list[object] = [
        func.lower(PriceItemRow.external_id) == keyword_query.normalized,
    ]
    if keyword_query.digits:
        conditions.append(PriceItemRow.supplier_inn == keyword_query.digits)

    if keyword_query.raw:
        conditions.append(
            PriceItemRow.supplier.ilike(_contains_pattern(keyword_query.raw)),
        )

    if keyword_query.term_groups:
        for column in (
            PriceItemRow.supplier,
            PriceItemRow.name,
            PriceItemRow.source_text,
            PriceItemRow.section,
            PriceItemRow.category,
            PriceItemRow.service_category,
            PriceItemRow.supplier_city,
            PriceItemRow.has_vat,
            PriceItemRow.supplier_status,
        ):
            conditions.append(
                _column_contains_term_groups(column, keyword_query.term_groups),
            )
    return conditions


def _column_contains_term_groups(
    column: object,
    term_groups: tuple[tuple[str, ...], ...],
) -> object:
    return and_(
        *[
            or_(
                *[
                    column.ilike(_contains_pattern(variant))  # type: ignore[attr-defined]
                    for variant in variants
                ],
            )
            for variants in term_groups
        ],
    )


def _keyword_fields_from_row(row: PriceItemRow) -> CatalogKeywordFields:
    return CatalogKeywordFields(
        external_id=row.external_id,
        name=row.name,
        source_text=row.source_text,
        section=row.section,
        category=row.category,
        service_category=row.service_category,
        supplier=row.supplier,
        supplier_inn=row.supplier_inn,
        supplier_city=row.supplier_city,
        has_vat=row.has_vat,
        supplier_status=row.supplier_status,
    )


def _contains_pattern(value: str) -> str:
    return f"%{value}%"


__all__ = ["SqlAlchemyPriceItemRepository"]
