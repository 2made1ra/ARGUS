# Data Model And CSV Import Plan

## Goal

Build the CSV-first catalog foundation for MVP: import files shaped like `prices.csv`, preserve raw rows, normalize searchable/card fields, generate `embedding_text`, and store `price_items` as the Postgres source of truth for the assistant and search tools.

## Target CSV Contract

The first supported import shape mirrors the provided `prices.csv`:

```text
id
name
category
unit
unit_price
source_text
created_at
section
supplier
has_vat
embedding
supplier_inn
supplier_city
supplier_phone
supplier_email
supplier_status
```

Rules:

- `embedding` is legacy data. Parse enough to record whether it exists and what dimension it has, but do not use it as the primary search vector.
- Keep raw CSV values for auditability.
- Store normalized values needed for filters, cards and deterministic `embedding_text`.
- Do not require document provenance in the MVP import path.
- Protect the catalog from repeated exact duplicates during CSV re-imports with a deterministic `row_fingerprint`.

## New PostgreSQL Tables

### `price_imports`

`price_imports.id` is the `import_batch_id` used by `price_items`.

```sql
id                          uuid primary key
source_file_id              uuid not null
filename                    text not null
source_path                 text null
file_sha256                 text null
schema_version              text not null default 'prices_csv_v1'
embedding_template_version  text not null default 'prices_v1'
embedding_model             text not null default 'nomic-embed-text-v1.5'
row_count                   integer not null default 0
valid_row_count             integer not null default 0
invalid_row_count           integer not null default 0
status                      text not null
error_message               text null
created_at                  timestamptz not null default now()
completed_at                timestamptz null
```

Allowed statuses:

```text
QUEUED | PROCESSING | IMPORTED | FAILED
```

`source_file_id` is a catalog-owned UUID for the imported file. It does not require a new global file service in MVP.

### `price_import_rows`

```sql
id                          uuid primary key
import_batch_id             uuid not null references price_imports(id) on delete cascade
source_file_id              uuid not null
row_number                  integer not null
raw                         jsonb not null
normalized                  jsonb null
legacy_embedding_dim        integer null
legacy_embedding_present    boolean not null default false
validation_warnings         jsonb not null default '[]'::jsonb
error_message               text null
price_item_id               uuid null references price_items(id) on delete set null
created_at                  timestamptz not null default now()
```

This table preserves every CSV row, including invalid rows and the raw `embedding` field. The application must not read legacy vectors from this table for user search in MVP.

### `price_items`

```sql
id                          uuid primary key
external_id                 text null
name                        text not null
category                    text null
category_normalized         text null
unit                        text not null
unit_normalized             text null
unit_price                  numeric(14, 2) not null
source_text                 text null
section                     text null
section_normalized          text null
supplier                    text null
has_vat                     text null
vat_mode                    text null
supplier_inn                text null
supplier_city               text null
supplier_city_normalized    text null
supplier_phone              text null
supplier_email              text null
supplier_status             text null
supplier_status_normalized  text null
import_batch_id             uuid not null references price_imports(id) on delete restrict
source_file_id              uuid not null
source_import_row_id        uuid null references price_import_rows(id) on delete set null
row_fingerprint             text not null
is_active                   boolean not null default true
superseded_at               timestamptz null
embedding_text              text not null
embedding_model             text not null
embedding_template_version  text not null default 'prices_v1'
catalog_index_status        text not null
embedding_error             text null
indexing_error              text null
indexed_at                  timestamptz null
legacy_embedding_present    boolean not null default false
legacy_embedding_dim        integer null
created_at                  timestamptz not null default now()
updated_at                  timestamptz not null default now()
```

Allowed `catalog_index_status` values:

```text
pending | indexed | embedding_failed | indexing_failed
```

The generated catalog vector is not stored in Postgres in MVP. `IndexPriceItemsUseCase` generates the vector from `embedding_text`, validates the dimension, upserts it into Qdrant, and then sets `catalog_index_status = indexed`. Use `embedding_failed` only when vector generation fails and `indexing_failed` only when Qdrant upsert fails.

MVP rows are CSV-derived only. Document-derived rows are introduced later with additional nullable provenance fields or a broader source table migration.

### `price_item_sources`

Keep provenance simple in MVP:

```sql
id                      uuid primary key
price_item_id           uuid not null references price_items(id) on delete cascade
source_kind             text not null default 'csv_import'
import_batch_id         uuid not null references price_imports(id) on delete restrict
source_file_id          uuid not null
price_import_row_id     uuid null references price_import_rows(id) on delete set null
source_text             text null
created_at              timestamptz not null default now()
```

Allowed MVP `source_kind`:

```text
csv_import
```

Post-MVP document provenance can extend this table with `document_id`, page, chunk and confidence fields.

### MVP Indexes And Constraints

Add only indexes needed for import, hydration and simple filters:

```sql
create unique index ux_price_imports_file_sha256_not_null on price_imports(file_sha256) where file_sha256 is not null;
create index ix_price_import_rows_import_batch_id on price_import_rows(import_batch_id);
create index ix_price_import_rows_price_item_id on price_import_rows(price_item_id);
create index ix_price_items_row_fingerprint_active on price_items(row_fingerprint) where is_active = true;
create index ix_price_items_catalog_index_status on price_items(catalog_index_status);
create index ix_price_items_supplier_city_normalized on price_items(supplier_city_normalized);
create index ix_price_items_category_normalized on price_items(category_normalized);
create index ix_price_items_supplier_status_normalized on price_items(supplier_status_normalized);
create index ix_price_items_supplier_inn on price_items(supplier_inn);
```

The `row_fingerprint` index is not a full dedupe/merge system. It only prevents exact active duplicates and supports linking repeated import rows back to an existing `price_item`.

## CSV Normalization Rules

- `id`: store as `external_id`; generate internal UUID for `price_items.id`.
- `name`: required; trim whitespace; collapse repeated spaces.
- `category`: nullable; trim; derive `category_normalized` with lowercasing and repeated-space collapse.
- `unit`: required; trim; derive `unit_normalized` for values such as `шт`, `шт.`, `ед`, `Nos`, `усл.`.
- `unit_price`: required numeric; accept spaces and comma decimals; reject if not numeric.
- `source_text`: nullable; preserve multiline text; include it in `embedding_text` only by the deterministic rules below.
- `created_at`: preserve in `price_import_rows.raw`; do not override database timestamps.
- `section`: nullable; trim; derive `section_normalized`.
- `supplier`: nullable; trim; do not require contractor resolution in MVP.
- `has_vat`: preserve raw; derive coarse `vat_mode` such as `with_vat`, `without_vat`, `unknown`.
- `embedding`: parse only to detect presence and dimension; store raw in `price_import_rows.raw`; do not index it.
- `supplier_inn`: strip non-digits for normalized storage; preserve unusual lengths with validation warnings.
- `supplier_city`: nullable; trim; derive `supplier_city_normalized` for filters.
- `supplier_phone`: trim and preserve raw; do not include in `embedding_text`.
- `supplier_email`: trim; lowercase only when it parses as a simple email; do not include in `embedding_text`.
- `supplier_status`: trim; derive `supplier_status_normalized`, defaulting to raw lowercased text.

## Re-Import And Duplicate Policy

MVP does not need a full dedupe/merge UI, but it must avoid inflating search results with exact duplicate rows.

Rules:

- Store `file_sha256` for each imported file.
- If the same file hash was already imported successfully, return the existing import summary or create an import record with a clear duplicate warning, but do not create duplicate `price_items`.
- Compute `row_fingerprint` from normalized catalog facts:

```text
name
category_normalized
unit_normalized
unit_price
supplier
supplier_inn
supplier_city_normalized
source_text
```

- If an active `price_items` row already has the same `row_fingerprint`, link the new `price_import_rows.price_item_id` to the existing item and do not create a duplicate item.
- If `external_id` matches but normalized price or descriptive fields changed, create a new active row in MVP and preserve the previous row. Automatic version merge, supersede decisions and manual dedupe review are post-MVP.
- `is_active` and `superseded_at` exist so later merge/version workflows can hide old rows without losing provenance.

## `embedding_text` Contract

Every valid `price_items` row must have deterministic `embedding_text` before indexing:

```text
Название: {name}
Категория: {category}
Раздел: {section}
Описание / источник: {source_text}
Единица измерения: {unit}
```

Rules:

- Omit empty lines.
- Template version is `prices_v1`.
- Include `source_text` only when all conditions are true:
  - it is non-empty after trimming;
  - it is not equal to `Ручной ввод` after case-insensitive normalization;
  - normalized `source_text` is not equal to normalized `name`.
- Do not include `unit_price`, `supplier_phone`, `supplier_email` or `supplier_inn`.
- Do not include `supplier_city`; store city as payload/filter.
- Do not include raw legacy embedding.

## Backend File Map

### Create

- `backend/app/features/catalog/__init__.py` - package marker.
- `backend/app/features/catalog/entities/__init__.py` - entity exports.
- `backend/app/features/catalog/entities/price_item.py` - `PriceItem`, `PriceImport`, `PriceImportRow`, `PriceItemSource`, enums.
- `backend/app/features/catalog/csv_parser.py` - CSV parsing with multiline fields through `csv.DictReader`.
- `backend/app/features/catalog/normalization.py` - pure normalization and validation functions.
- `backend/app/features/catalog/embedding_text.py` - deterministic `prices_v1` template.
- `backend/app/features/catalog/ports.py` - repositories, vector index/search and embedding protocols.
- `backend/app/features/catalog/use_cases/import_prices_csv.py` - CSV import orchestration.
- `backend/app/features/catalog/use_cases/list_price_items.py` - paginated catalog list.
- `backend/app/features/catalog/use_cases/get_price_item.py` - item detail with CSV provenance.
- `backend/app/adapters/sqlalchemy/price_imports.py` - import repositories.
- `backend/app/adapters/sqlalchemy/price_items.py` - item repositories.
- `backend/app/entrypoints/http/catalog.py` - catalog API router.
- `backend/app/entrypoints/http/schemas/catalog.py` - HTTP DTOs.
- `backend/migrations/versions/0004_catalog_price_items.py` - MVP catalog tables and indexes.

### Modify

- `backend/app/adapters/sqlalchemy/models.py` - add ORM models.
- `backend/app/entrypoints/http/router.py` - include catalog router.
- `backend/app/entrypoints/http/dependencies.py` - construct catalog use cases.
- `docs/api/openapi.yaml` - add catalog endpoints during implementation phase.
- `docs/agent/data-model.md` - record catalog tables during implementation phase.

## API Contract

### `POST /catalog/imports`

Accepts CSV file upload and returns import summary.

```json
{
  "id": "uuid-import-batch",
  "source_file_id": "uuid-source-file",
  "filename": "prices.csv",
  "status": "IMPORTED",
  "row_count": 1565,
  "valid_row_count": 1565,
  "invalid_row_count": 0,
  "embedding_template_version": "prices_v1",
  "embedding_model": "nomic-embed-text-v1.5"
}
```

### `GET /catalog/items`

Returns paginated rows for admin/catalog table and assistant hydration.

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Аренда акустической системы",
      "category": "Аренда",
      "unit": "день",
      "unit_price": "15000.00",
      "supplier": "ООО Пример",
      "supplier_inn": "7700000000",
      "supplier_city": "г. Москва",
      "has_vat": "Без НДС",
      "supplier_status": "Активен",
      "catalog_index_status": "indexed",
      "import_batch_id": "uuid-import-batch",
      "source_file_id": "uuid-source-file"
    }
  ],
  "total": 1
}
```

### `GET /catalog/items/{id}`

Returns full row detail and CSV provenance.

```json
{
  "item": {
    "id": "uuid",
    "name": "Аренда акустической системы",
    "category": "Аренда",
    "unit": "день",
    "unit_price": "15000.00",
    "source_text": "исходный фрагмент строки",
    "supplier": "ООО Пример",
    "supplier_city": "г. Москва",
    "embedding_text": "Название: ...",
    "embedding_template_version": "prices_v1"
  },
  "sources": [
    {
      "source_kind": "csv_import",
      "import_batch_id": "uuid-import-batch",
      "source_file_id": "uuid-source-file",
      "row_number": 42
    }
  ]
}
```

## Testing Plan

- [ ] Add `backend/tests/features/catalog/test_csv_parser.py` for multiline `source_text`, empty `category`, empty `source_text` and raw `embedding` preservation.
- [ ] Add `backend/tests/features/catalog/test_normalization.py` for price parsing, VAT mode, city normalization, unit normalization, INN warnings and required fields.
- [ ] Add `backend/tests/features/catalog/test_embedding_text.py` for deterministic `prices_v1` output, excluded fields and deterministic `source_text` inclusion cases.
- [ ] Add `backend/tests/features/catalog/use_cases/test_import_prices_csv.py` for `price_imports`, `price_import_rows`, `price_items`, `source_file_id`, `import_batch_id`, legacy embedding metadata, repeated `file_sha256` behavior and `row_fingerprint` duplicate protection.
- [ ] Add `backend/tests/adapters/sqlalchemy/test_price_items.py` for repository add/list/get/source operations.
- [ ] Add `backend/tests/entrypoints/http/test_catalog.py` for import, list and detail endpoints.

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/catalog/test_csv_parser.py -v
uv run --project backend pytest backend/tests/features/catalog/test_normalization.py -v
uv run --project backend pytest backend/tests/features/catalog/test_embedding_text.py -v
uv run --project backend pytest backend/tests/features/catalog/use_cases/test_import_prices_csv.py -v
uv run --project backend pytest backend/tests/adapters/sqlalchemy/test_price_items.py -v
uv run --project backend pytest backend/tests/entrypoints/http/test_catalog.py -v
```
