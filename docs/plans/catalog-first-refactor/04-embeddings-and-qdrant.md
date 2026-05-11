# Embeddings And Qdrant Plan

## Goal

Make new, controlled catalog embeddings the only primary vector space for MVP search. Legacy CSV embeddings remain stored for audit/post-MVP auxiliary workflows but are not used for user query search.

## Embedding Contract

```text
collection: price_items_search_v1
primary object: price_items.id
primary vector: new embedding generated from price_items.embedding_text
embedding template: prices_v1
embedding model: nomic-embed-text-v1.5 for MVP unless the project config is deliberately changed
dimension: configured catalog embedding dimension for that model
storage: vector is stored in Qdrant only, not in Postgres
primary evidence: hydrated Postgres price_items row
```

Rules:

- Do not infer catalog embedding dimension from the CSV legacy `embedding` column.
- Do not mix document chunk vectors and catalog row vectors in one collection.
- Do not query legacy vectors with new query embeddings.
- Reindex all catalog rows when `embedding_model`, `embedding_dim`, `embedding_template_version`, document prefix or query prefix changes.

## Configuration

Modify `backend/app/config.py` to split document and catalog vector settings:

```python
document_qdrant_collection: str = "document_chunks"
document_embedding_dim: int = 768
catalog_qdrant_collection: str = "price_items_search_v1"
catalog_embedding_model: str = "nomic-embed-text-v1.5"
catalog_embedding_dim: int = 768
catalog_embedding_template_version: str = "prices_v1"
catalog_document_prefix: str = "search_document: "
catalog_query_prefix: str = "search_query: "
```

The exact `catalog_embedding_dim` must match the selected embedding model. It is intentionally not copied from legacy CSV vectors.

Current usages:

- existing document search/indexing uses `document_qdrant_collection`;
- catalog import/index/search uses `catalog_qdrant_collection`;
- catalog embedding client validates vectors against `catalog_embedding_dim`;
- catalog indexing embeds `catalog_document_prefix + embedding_text`;
- catalog search embeds `catalog_query_prefix + user_query`;
- Qdrant bootstrap creates `price_items_search_v1` independently from `document_chunks`.

For `nomic-embed-text-v1.5`, task prefixes are part of the embedding contract: catalog rows use `search_document:` and user queries use `search_query:`. Stored `price_items.embedding_text` remains unprefixed so it is deterministic and inspectable; the embedding client applies the configured prefix at generation time. If the project switches to another embedding model, the prefix contract must be reviewed as model-specific config.

## Catalog Embedding Text Template

Use this deterministic template for `prices_v1`:

```text
Название: {name}
Категория: {category}
Раздел: {section}
Описание / источник: {source_text}
Единица измерения: {unit}
```

Rules:

- Omit empty values line-by-line.
- Preserve meaningful Russian source wording.
- Include `source_text` only when all conditions are true:
  - it is non-empty after trimming;
  - it is not equal to `Ручной ввод` after case-insensitive normalization;
  - normalized `source_text` is not equal to normalized `name`.
- Do not include `unit_price`.
- Do not include `supplier_phone`.
- Do not include `supplier_email`.
- Do not include `supplier_inn`.
- Do not include `supplier_city`; use it as a filter/payload field.
- Do not include raw legacy embedding arrays.

## Indexing Flow

```text
price_items row
  -> embedding_text prices_v1
  -> catalog embedding client embeds "search_document: " + embedding_text
  -> vector dimension validation
  -> Qdrant point id = price_items.id
  -> payload with filter/card fields
  -> upsert into price_items_search_v1
  -> set catalog_index_status = indexed
```

Failure rules:

- If embedding generation fails, keep the `price_items` row and set `catalog_index_status = embedding_failed` with `embedding_error`.
- If Qdrant upsert fails, keep the row and set `catalog_index_status = indexing_failed` with `indexing_error`.
- Search only returns rows with indexed points.
- There is no persistent `generated` status in MVP. Generation and Qdrant upsert are one indexing use case, so no intermediate vector storage is needed.

## Qdrant Payload

Payload is for filtering and lightweight result mapping, not for full card truth.

```json
{
  "price_item_id": "uuid",
  "import_batch_id": "uuid",
  "source_file_id": "uuid",
  "category": "Аренда",
  "section": "Оборудование",
  "unit": "день",
  "unit_price": 15000.0,
  "has_vat": "Без НДС",
  "vat_mode": "without_vat",
  "supplier": "ООО Пример",
  "supplier_city": "г. Москва",
  "supplier_status": "Активен",
  "embedding_model": "nomic-embed-text-v1.5",
  "embedding_template_version": "prices_v1"
}
```

Full card fields are hydrated from Postgres after vector search.

## Payload Indexes

Create payload indexes only for fields used in MVP filters:

```text
price_item_id
import_batch_id
source_file_id
category
section
unit
unit_price
has_vat
vat_mode
supplier_city
supplier_status
embedding_template_version
```

Do not add sparse-vector or named-vector indexes in MVP.

## Search Flow

```text
search_items(query, filters, limit)
  -> generate query embedding from "search_query: " + query with same catalog model
  -> search price_items_search_v1 with payload filters
  -> run minimal Postgres keyword fallback for exact names/suppliers/INN/source text
  -> merge and dedupe candidate price_item_id values
  -> get price_item_id and score
  -> hydrate rows from Postgres
  -> preserve semantic ranking first and append keyword-only matches unless product ranking rules say otherwise
  -> return catalog item cards to assistant/UI
```

Minimum keyword fallback is part of MVP because users will search for supplier names, INNs, exact model names and exact service names. It can use existing Postgres capabilities over `name`, `source_text`, `supplier`, `supplier_inn` and `external_id`. Full hybrid ranking, sparse vectors, RRF and metric-driven ranking experiments are post-MVP.

## Legacy Embeddings Policy

CSV legacy embeddings can be useful later, but not for primary search.

MVP behavior:

- keep raw `embedding` in `price_import_rows.raw`;
- record `legacy_embedding_present` and `legacy_embedding_dim`;
- do not upsert legacy vectors to `price_items_search_v1`;
- do not configure named vectors;
- do not compare user query vectors against legacy vectors.

Post-MVP auxiliary use cases:

- duplicate detection inside old CSV imports;
- "similar rows to this existing row" using a legacy vector from the same vector space;
- clustering old positions;
- comparing quality of the new `prices_v1` embedding scheme;
- import QA warnings.

## Backend File Map

### Create

- `backend/app/adapters/qdrant/catalog_index.py` - upsert/delete `price_items_search_v1` points.
- `backend/app/adapters/qdrant/catalog_search.py` - search `price_items_search_v1` with payload filters.
- `backend/app/features/catalog/use_cases/index_price_items.py` - generate embeddings and index rows.
- `backend/app/features/catalog/use_cases/search_price_items.py` - query embedding, Qdrant search and Postgres hydration.

### Modify

- `backend/app/config.py` - add catalog vector settings.
- `backend/app/adapters/qdrant/bootstrap.py` - bootstrap both document and catalog collections.
- `backend/app/adapters/llm/embeddings.py` - support separate document/catalog clients through config, without hardcoding one dimension.
- `backend/app/entrypoints/http/dependencies.py` - inject catalog embedding, index and search dependencies.
- `backend/app/entrypoints/celery/composition.py` - inject catalog index use case only when background indexing is introduced.
- `backend/tests/adapters/qdrant/test_bootstrap.py` - assert `price_items_search_v1` settings and payload indexes.

## Testing Plan

- [ ] Add `backend/tests/features/catalog/test_embedding_text.py` for deterministic `prices_v1` output, excluded fields and deterministic `source_text` inclusion.
- [ ] Add `backend/tests/features/catalog/use_cases/test_index_price_items.py` for document-prefix embedding input, vector success, `embedding_failed`, `indexing_failed` and no Postgres vector persistence.
- [ ] Add `backend/tests/features/catalog/use_cases/test_search_price_items.py` for query-prefix embedding input, Qdrant ranking, Postgres hydration, keyword fallback, filters and empty results.
- [ ] Add `backend/tests/adapters/qdrant/test_catalog_index.py` for point id, vector dimension and payload.
- [ ] Add `backend/tests/adapters/qdrant/test_catalog_search.py` for filter conversion and result mapping.
- [ ] Update `backend/tests/test_config.py` for catalog vector defaults.
- [ ] Update `backend/tests/adapters/qdrant/test_bootstrap.py` for `price_items_search_v1`.

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/catalog/test_embedding_text.py -v
uv run --project backend pytest backend/tests/features/catalog/use_cases/test_index_price_items.py -v
uv run --project backend pytest backend/tests/features/catalog/use_cases/test_search_price_items.py -v
uv run --project backend pytest backend/tests/adapters/qdrant/test_catalog_index.py backend/tests/adapters/qdrant/test_catalog_search.py -v
uv run --project backend pytest backend/tests/test_config.py backend/tests/adapters/qdrant/test_bootstrap.py -v
```
