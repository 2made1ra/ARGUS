from __future__ import annotations

import re
from dataclasses import dataclass

from app.features.catalog.dto import MatchReasonCode, SearchPriceItemsFilters
from app.features.catalog.entities.price_item import PriceItem


@dataclass(frozen=True, slots=True)
class CatalogKeywordFields:
    external_id: str | None
    name: str | None
    source_text: str | None
    section: str | None
    category: str | None
    supplier: str | None
    supplier_inn: str | None
    supplier_city: str | None
    has_vat: str | None
    supplier_status: str | None


@dataclass(frozen=True, slots=True)
class KeywordQuery:
    raw: str
    normalized: str
    digits: str | None
    term_groups: tuple[tuple[str, ...], ...]


def build_keyword_query(query: str) -> KeywordQuery:
    normalized = _normalize_text(query)
    terms = tuple(_term_variants(term) for term in normalized.split() if term)
    digits = _digits_only(query) or None
    return KeywordQuery(
        raw=query.strip(),
        normalized=normalized,
        digits=digits,
        term_groups=terms,
    )


def price_item_keyword_fields(item: PriceItem) -> CatalogKeywordFields:
    return CatalogKeywordFields(
        external_id=item.external_id,
        name=item.name,
        source_text=item.source_text,
        section=item.section,
        category=item.category,
        supplier=item.supplier,
        supplier_inn=item.supplier_inn,
        supplier_city=item.supplier_city,
        has_vat=item.has_vat,
        supplier_status=item.supplier_status,
    )


def keyword_reason_for_fields(
    fields: CatalogKeywordFields,
    query: KeywordQuery,
) -> MatchReasonCode | None:
    if fields.external_id is not None:
        if _normalize_text(fields.external_id) == query.normalized:
            return "keyword_external_id"

    if query.digits and fields.supplier_inn == query.digits:
        return "keyword_inn"

    if _contains_query(fields.supplier, query) or _contains_term_groups(
        fields.supplier,
        query.term_groups,
    ):
        return "keyword_supplier"

    if _contains_term_groups(fields.name, query.term_groups):
        return "keyword_name"

    if _contains_term_groups(fields.source_text, query.term_groups):
        return "keyword_source_text"

    if any(
        _contains_term_groups(value, query.term_groups)
        for value in (
            fields.section,
            fields.category,
            fields.supplier_city,
            fields.has_vat,
            fields.supplier_status,
        )
    ):
        return "keyword_source_text"

    return None


def keyword_score(reason: MatchReasonCode) -> float:
    scores: dict[MatchReasonCode, float] = {
        "keyword_external_id": 0.72,
        "keyword_inn": 0.7,
        "keyword_supplier": 0.62,
        "keyword_name": 0.58,
        "keyword_source_text": 0.5,
        "semantic": 0.0,
    }
    return scores[reason]


def infer_search_filters_from_query(query: str) -> SearchPriceItemsFilters:
    normalized = _normalize_text(query)
    has_vat = None
    vat_mode = None
    if "без" in normalized and "ндс" in normalized:
        has_vat = "Без НДС"
        vat_mode = "without_vat"

    supplier_city_normalized = None
    if _contains_city_alias(normalized):
        supplier_city_normalized = "екатеринбург"

    supplier_status_normalized = None
    if "актив" in normalized and "неактив" not in normalized:
        supplier_status_normalized = "активен"

    return SearchPriceItemsFilters(
        supplier_city_normalized=supplier_city_normalized,
        has_vat=has_vat,
        vat_mode=vat_mode,
        supplier_status_normalized=supplier_status_normalized,
    )


def merge_search_filters(
    base: SearchPriceItemsFilters,
    inferred: SearchPriceItemsFilters,
) -> SearchPriceItemsFilters:
    return SearchPriceItemsFilters(
        supplier_city=_pick(base.supplier_city, inferred.supplier_city),
        supplier_city_normalized=(
            _pick(base.supplier_city_normalized, inferred.supplier_city_normalized)
        ),
        category=_pick(base.category, inferred.category),
        category_normalized=_pick(
            base.category_normalized,
            inferred.category_normalized,
        ),
        section=_pick(base.section, inferred.section),
        section_normalized=_pick(
            base.section_normalized,
            inferred.section_normalized,
        ),
        supplier_status=_pick(base.supplier_status, inferred.supplier_status),
        supplier_status_normalized=(
            _pick(
                base.supplier_status_normalized,
                inferred.supplier_status_normalized,
            )
        ),
        has_vat=_pick(base.has_vat, inferred.has_vat),
        vat_mode=_pick(base.vat_mode, inferred.vat_mode),
        unit_price=_pick(base.unit_price, inferred.unit_price),
        unit_price_min=_pick(base.unit_price_min, inferred.unit_price_min),
        unit_price_max=_pick(base.unit_price_max, inferred.unit_price_max),
    )


def price_item_matches_filters(
    item: PriceItem,
    filters: SearchPriceItemsFilters,
) -> bool:
    if (
        filters.supplier_city is not None
        and item.supplier_city != filters.supplier_city
    ):
        return False
    if (
        filters.supplier_city_normalized is not None
        and item.supplier_city_normalized != filters.supplier_city_normalized
    ):
        return False
    if filters.category is not None and item.category != filters.category:
        return False
    if (
        filters.category_normalized is not None
        and item.category_normalized != filters.category_normalized
    ):
        return False
    if filters.section is not None and item.section != filters.section:
        return False
    if (
        filters.section_normalized is not None
        and item.section_normalized != filters.section_normalized
    ):
        return False
    if (
        filters.supplier_status is not None
        and item.supplier_status != filters.supplier_status
    ):
        return False
    if (
        filters.supplier_status_normalized is not None
        and item.supplier_status_normalized != filters.supplier_status_normalized
    ):
        return False
    if filters.has_vat is not None and item.has_vat != filters.has_vat:
        return False
    if filters.vat_mode is not None and item.vat_mode != filters.vat_mode:
        return False
    if filters.unit_price is not None and item.unit_price != filters.unit_price:
        return False
    if filters.unit_price_min is not None and item.unit_price < filters.unit_price_min:
        return False
    return not (
        filters.unit_price_max is not None
        and item.unit_price > filters.unit_price_max
    )


def _contains_query(value: str | None, query: KeywordQuery) -> bool:
    if value is None or not query.normalized:
        return False
    return query.normalized in _normalize_text(value)


def _contains_term_groups(
    value: str | None,
    term_groups: tuple[tuple[str, ...], ...],
) -> bool:
    if value is None or not term_groups:
        return False
    normalized = _normalize_text(value)
    return all(
        any(variant in normalized for variant in variants)
        for variants in term_groups
    )


def _term_variants(term: str) -> tuple[str, ...]:
    stripped = term.strip(".,;:!?()[]{}\"'«»")
    variants = [term]
    if stripped and stripped != term:
        variants.append(stripped)

    for value in tuple(variants):
        if len(value) < 4 or not re.search("[а-я]", value):
            continue
        if value.endswith(("ы", "и")):
            variants.append(value[:-1])
            variants.append(f"{value[:-1]}а")
        elif value.endswith(("а", "я")):
            variants.append(value[:-1])

    return tuple(dict.fromkeys(variant for variant in variants if variant))


def _contains_city_alias(normalized: str) -> bool:
    aliases = ("екат", "екб", "екатеринбург")
    return any(alias in normalized for alias in aliases)


def _pick[T](base: T | None, inferred: T | None) -> T | None:
    return base if base is not None else inferred


def _normalize_text(value: str) -> str:
    normalized = value.replace("ё", "е").replace("Ё", "е")
    return re.sub(r"\s+", " ", normalized.strip()).casefold()


def _digits_only(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


__all__ = [
    "CatalogKeywordFields",
    "KeywordQuery",
    "build_keyword_query",
    "infer_search_filters_from_query",
    "keyword_reason_for_fields",
    "keyword_score",
    "merge_search_filters",
    "price_item_keyword_fields",
    "price_item_matches_filters",
]
