# Data Model

ARGUS MVP is catalog-first for event agency managers. Postgres `price_items` is
the source of truth for catalog facts. Document tables remain the source of
truth for uploaded PDFs/contracts and are not replaced by the catalog.

Assistant state is an application/API contract, not a catalog source of truth.
`BriefState`, `ActionPlan`, `found_items`, `verification_results` and
`rendered_brief` may be returned by `POST /assistant/chat`, but catalog facts
still come from hydrated `price_items`, opened item details or explicit
verification results.

## PostgreSQL tables

### Catalog MVP tables

**price_imports**
```sql
id                          uuid PK
source_file_id              uuid
filename                    text
source_path                 text
file_sha256                 text
schema_version              text       -- prices_csv_v1
embedding_template_version  text       -- prices_v1
embedding_model             text       -- e.g. nomic-embed-text-v1.5
row_count                   integer
valid_row_count             integer
invalid_row_count           integer
status                      text       -- QUEUED | PROCESSING | IMPORTED | FAILED
error_message               text
created_at                  timestamptz
completed_at                timestamptz
```

Use `file_sha256` to avoid accidental duplicate imports of the same CSV file.

**price_import_rows**
```sql
id                          uuid PK
import_batch_id             uuid FK -> price_imports.id
source_file_id              uuid
row_number                  integer
raw                         jsonb       -- full CSV row, including legacy embedding
normalized                  jsonb
legacy_embedding_dim        integer
legacy_embedding_present    boolean
validation_warnings         jsonb
error_message               text
price_item_id               uuid FK -> price_items.id
created_at                  timestamptz
```

CSV legacy `embedding` stays in raw/audit data only. Do not use it for user query
search and do not infer catalog embedding dimension from it.

**price_items**
```sql
id                          uuid PK
external_id                 text        -- CSV id
name                        text
category                    text
category_normalized         text
unit                        text
unit_normalized             text
unit_price                  numeric(14, 2)
source_text                 text
section                     text
section_normalized          text
supplier                    text
has_vat                     text
vat_mode                    text
supplier_inn                text
supplier_city               text
supplier_city_normalized    text
supplier_phone              text
supplier_email              text
supplier_status             text
supplier_status_normalized  text
import_batch_id             uuid FK -> price_imports.id
source_file_id              uuid
source_import_row_id        uuid FK -> price_import_rows.id
row_fingerprint             text
is_active                   boolean
superseded_at               timestamptz
embedding_text              text
embedding_model             text
embedding_template_version  text        -- prices_v1
catalog_index_status        text        -- pending | indexed | embedding_failed | indexing_failed
embedding_error             text
indexing_error              text
indexed_at                  timestamptz
legacy_embedding_present    boolean
legacy_embedding_dim        integer
created_at                  timestamptz
updated_at                  timestamptz
```

`supplier_status` on `price_items` is a catalog field from the source row. It is
not the same as supplier verification output and must not be presented as
registry proof unless a verification tool result confirms it.

Generated catalog vectors are not stored in Postgres for MVP. Prefer one
generate+index flow: `embedding_text -> embedding generation -> dimension
validation -> Qdrant upsert -> catalog_index_status`. Persist generated vectors
only if a separate vector storage contract is deliberately introduced.

Distinguish failures:

- `embedding_failed`: the embedding model/client failed or returned an invalid
  vector.
- `indexing_failed`: Qdrant upsert/bootstrap failed after a vector was produced.

**price_item_sources**
```sql
id                      uuid PK
price_item_id           uuid FK -> price_items.id
source_kind             text        -- csv_import in MVP
import_batch_id         uuid FK -> price_imports.id
source_file_id          uuid
price_import_row_id     uuid FK -> price_import_rows.id
source_text             text
created_at              timestamptz
```

Post-MVP document provenance can extend this with `document_id`, page, chunk and
confidence fields, but document extraction must still write catalog-compatible
`price_items` before those rows become catalog search evidence.

### CSV duplicate policy

MVP does not need manual dedupe/merge UI, but repeated imports must not inflate
active search results:

- Store `file_sha256` for imported CSV files.
- If a successful import already has the same file hash, return the existing
  import summary or a duplicate warning; do not create duplicate active items.
- Compute `row_fingerprint` from normalized catalog facts: `name`,
  `category_normalized`, `unit_normalized`, `unit_price`, `supplier`,
  `supplier_inn`, `supplier_city_normalized`, and `source_text`.
- If an active row has the same `row_fingerprint`, link the new import row to
  the existing `price_items.id`.
- If `external_id` matches but price or descriptive fields changed, preserve a
  new active row in MVP. Version merging/superseding is post-MVP.

### `embedding_text prices_v1`

Every valid catalog item gets deterministic unprefixed text:

```text
Название: {name}
Категория: {category}
Раздел: {section}
Описание / источник: {source_text}
Единица измерения: {unit}
```

Rules:

- Omit empty lines.
- Do not include `unit_price`, `supplier_phone`, `supplier_email`,
  `supplier_inn`, `supplier_city` or raw legacy embedding.
- Include `source_text` only when it is non-empty after trimming, is not
  `Ручной ввод` after case-insensitive normalization, and is not equal to
  `name` after normalization.

`nomic-embed-text-v1.5` requires task prefixes at embedding time:

- catalog row indexing input: `"search_document: " + embedding_text`
- user query input: `"search_query: " + query`

Changing model, dimension, template version or either prefix requires catalog
reindexing.

### Existing document tables

**contractors**
```sql
id              uuid PK
display_name    text
normalized_key  text UNIQUE       -- canonical matching key
inn             text              -- primary dedup key, nullable
kpp             text
created_at      timestamptz
```

**contractor_raw_mappings**
```sql
id                   uuid PK
raw_name             text
inn                  text
contractor_entity_id uuid FK → contractors.id
confidence           float         -- 1.0=exact, <1.0=fuzzy
```

**documents**
```sql
id                   uuid PK
contractor_entity_id uuid FK → contractors.id, nullable
title                text
file_path            text
content_type         text
document_kind        text          -- "text" | "scan"
doc_type             text          -- "contract" | "act" | "invoice" | ...
status               text          -- QUEUED | PROCESSING | RESOLVING | INDEXING | INDEXED | FAILED
error_message        text          -- null unless status=FAILED
partial_extraction   bool          -- true if LLM extraction was incomplete
preview_file_path    text          -- path to PDF preview (nullable, added migration 3)
created_at           timestamptz
```

**document_chunks**
```sql
id              uuid PK
document_id     uuid FK → documents.id
chunk_index     int
text            text
page_start      int
page_end        int
section_type    text
chunk_summary   text
```

**extracted_fields**
```sql
id          uuid PK
document_id uuid FK → documents.id UNIQUE
fields      jsonb       -- ContractFields as JSON
created_at  timestamptz
```

**document_summaries**
```sql
id          uuid PK
document_id uuid FK → documents.id UNIQUE
summary     text
key_points  text[]
created_at  timestamptz
```

## Qdrant collection: `document_chunks`

**Payload per vector:**
```json
{
  "document_id":           "uuid",
  "contractor_entity_id":  "uuid",
  "doc_type":              "contract",
  "document_kind":         "text",
  "date":                  "2025-01-15",
  "page_start":            3,
  "page_end":              4,
  "section_type":          "body",
  "chunk_index":           7,
  "text":                  "...",
  "is_summary":            false
}
```

Document-level summary: stored as a chunk with `is_summary: true`, `chunk_index: -1`.

## Qdrant collection: `price_items_search_v1`

Catalog search uses a separate collection from document chunks.

```text
collection: price_items_search_v1
point id: price_items.id
vector: new catalog embedding from prices_v1 embedding_text
payload: filter and lightweight mapping fields
```

Payload example:

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

Full cards are hydrated from Postgres `price_items`. Do not mix
`document_chunks` vectors and `price_items` vectors in the same Qdrant
collection.

## Assistant State Contracts

Assistant state is carried through request/response DTOs for the event-brief
copilot. It should not be conflated with Postgres catalog persistence unless a
future task explicitly introduces event/session storage.

Target `BriefState` v2:

```json
{
  "event_type": null,
  "event_goal": null,
  "concept": null,
  "format": null,
  "city": null,
  "date_or_period": null,
  "audience_size": null,
  "venue": null,
  "venue_status": null,
  "venue_constraints": [],
  "duration_or_time_window": null,
  "event_level": null,
  "budget_total": null,
  "budget_per_guest": null,
  "budget_notes": null,
  "catering_format": null,
  "technical_requirements": [],
  "service_needs": [],
  "required_services": [],
  "must_have_services": [],
  "nice_to_have_services": [],
  "selected_item_ids": [],
  "constraints": [],
  "preferences": [],
  "open_questions": []
}
```

Selection and candidate context:

- `found_items` are hydrated catalog candidates.
- `selected_item_ids` are explicit user choices.
- `visible_candidates` and `candidate_item_ids` come from the frontend request
  when the user refers to visible results.
- The backend must not resolve `второй вариант`, `первые два` or
  `найденных подрядчиков` from hidden server memory in the stateless first
  implementation.

Supplier verification output is separate from catalog rows:

```json
{
  "item_id": "uuid",
  "supplier_name": "ООО Пример",
  "supplier_inn": "7700000000",
  "ogrn": null,
  "legal_name": null,
  "status": "not_verified",
  "source": "manual_not_verified",
  "checked_at": null,
  "risk_flags": ["verification_adapter_not_configured"]
}
```

Allowed verification statuses:

```text
active | inactive | not_found | not_verified | error
```

`active` means the legal entity was active in the verification source. It does
not mean event-date availability, recommendation, booking confirmation or valid
agency contract.

## ContractFields (LLM extraction target)

Russian contract fields, all `Optional[str]`, never invented — null if not found:
`document_type`, `document_number`, `document_date`, `supplier_name`, `customer_name`,
`service_date`, `amount`, `vat`, `valid_until`, `supplier_inn`, `supplier_kpp`,
`supplier_bik`, `supplier_account`, `customer_inn`, `customer_kpp`, `customer_bik`,
`customer_account`, `service_subject`, `service_price`, `signatory_name`, `contact_phone`
