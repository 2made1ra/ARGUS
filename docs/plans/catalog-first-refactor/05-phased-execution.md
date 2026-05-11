# Phased Execution Plan

This plan starts after the `catalog-first-refactor` docs have been updated. It does not include a phase for rewriting this plan.

## Phase 1: `price_items` Persistence And CSV Import

**Outcome:** `prices.csv` can be imported into Postgres as raw rows plus normalized active `price_items`; legacy embeddings are preserved only as audit metadata; repeated exact rows do not inflate search results.

**Files:**

- Create: `backend/app/features/catalog/entities/price_item.py`
- Create: `backend/app/features/catalog/csv_parser.py`
- Create: `backend/app/features/catalog/normalization.py`
- Create: `backend/app/features/catalog/embedding_text.py`
- Create: `backend/app/features/catalog/ports.py`
- Create: `backend/app/features/catalog/use_cases/import_prices_csv.py`
- Create: `backend/app/features/catalog/use_cases/list_price_items.py`
- Create: `backend/app/features/catalog/use_cases/get_price_item.py`
- Create: `backend/app/adapters/sqlalchemy/price_imports.py`
- Create: `backend/app/adapters/sqlalchemy/price_items.py`
- Create: `backend/app/entrypoints/http/catalog.py`
- Create: `backend/app/entrypoints/http/schemas/catalog.py`
- Create: `backend/migrations/versions/0004_catalog_price_items.py`
- Modify: `backend/app/adapters/sqlalchemy/models.py`
- Modify: `backend/app/entrypoints/http/router.py`
- Modify: `backend/app/entrypoints/http/dependencies.py`
- Modify: `docs/api/openapi.yaml`
- Modify: `docs/agent/data-model.md`

**Steps:**

- [x] Write failing tests for CSV parsing: multiline `source_text`, empty `category`, empty `source_text`, raw `embedding` preservation.
- [x] Write failing tests for normalization: unit, VAT, city, price, INN warnings and required fields.
- [x] Write failing tests for deterministic `embedding_text prices_v1`, including `source_text` inclusion/exclusion:
  - empty source -> omitted;
  - `Ручной ввод` -> omitted;
  - same normalized text as `name` -> omitted;
  - meaningful description -> included.
- [x] Write failing import use case tests for `price_imports`, `price_import_rows`, `price_items`, `source_file_id`, `import_batch_id` and legacy embedding metadata.
- [x] Write failing duplicate-protection tests for repeated `file_sha256`, active `row_fingerprint` reuse and changed price/fields creating a new row.
- [x] Write failing repository tests for add/list/get/source operations.
- [x] Add ORM models and Alembic migration.
- [x] Add catalog entities and ports.
- [x] Implement CSV parser with `csv.DictReader`.
- [x] Implement pure normalization functions.
- [x] Implement `row_fingerprint` builder from normalized row facts.
- [x] Implement `embedding_text` builder.
- [x] Implement SQLAlchemy repositories.
- [x] Implement `ImportPricesCsvUseCase`.
- [x] Add `POST /catalog/imports`, `GET /catalog/items`, `GET /catalog/items/{id}`.
- [x] Update OpenAPI and `docs/agent/data-model.md`.
- [x] Run focused backend checks.

**Verification:**

```bash
uv run --project backend pytest backend/tests/features/catalog/test_csv_parser.py -v
uv run --project backend pytest backend/tests/features/catalog/test_normalization.py -v
uv run --project backend pytest backend/tests/features/catalog/test_embedding_text.py -v
uv run --project backend pytest backend/tests/features/catalog/use_cases/test_import_prices_csv.py -v
uv run --project backend pytest backend/tests/adapters/sqlalchemy/test_price_items.py -v
uv run --project backend pytest backend/tests/entrypoints/http/test_catalog.py -v
```

## Phase 2: Catalog Indexing Into `price_items_search_v1`

**Outcome:** Valid active catalog rows are embedded with the configured catalog model and indexed into Qdrant collection `price_items_search_v1`. The generated vector lives only in Qdrant.

**Files:**

- Create: `backend/app/features/catalog/use_cases/index_price_items.py`
- Create: `backend/app/adapters/qdrant/catalog_index.py`
- Create: `backend/app/adapters/qdrant/catalog_search.py`
- Modify: `backend/app/adapters/llm/embeddings.py`
- Modify: `backend/app/adapters/qdrant/bootstrap.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/entrypoints/http/dependencies.py`
- Modify: `docs/agent/data-model.md`
- Modify: `docs/agent/search.md`

**Steps:**

- [ ] Write failing tests proving the CSV legacy `embedding` is not used as the catalog vector.
- [ ] Write failing config/bootstrap tests for `price_items_search_v1`, catalog dimension and payload indexes.
- [ ] Write failing catalog index adapter tests for point id, vector dimension and payload.
- [ ] Write failing index use case tests for successful index, `embedding_failed`, `indexing_failed`, skipped inactive rows and no Postgres vector persistence.
- [ ] Write failing tests proving index input uses `catalog_document_prefix + embedding_text`.
- [ ] Split document and catalog embedding/vector config:
  - `catalog_qdrant_collection`;
  - `catalog_embedding_model`;
  - `catalog_embedding_dim`;
  - `catalog_embedding_template_version`;
  - `catalog_document_prefix`;
  - `catalog_query_prefix`.
- [ ] Add catalog embedding client dependency using catalog config.
- [ ] Extend Qdrant bootstrap for document and catalog collections.
- [ ] Implement catalog Qdrant index adapter.
- [ ] Implement catalog Qdrant search adapter result mapping.
- [ ] Implement `IndexPriceItemsUseCase` as one flow: `embedding_text` -> embedding generation -> dimension validation -> Qdrant upsert -> `catalog_index_status`.
- [ ] Set `catalog_index_status = indexed`, `embedding_failed` or `indexing_failed` with separate `embedding_error` and `indexing_error`.
- [ ] Add payload indexes for MVP filters.
- [ ] Update docs for Qdrant collection, prefix contract and payload contract.
- [ ] Run focused Qdrant/indexing checks.

**Verification:**

```bash
uv run --project backend pytest backend/tests/test_config.py backend/tests/adapters/qdrant/test_bootstrap.py -v
uv run --project backend pytest backend/tests/adapters/qdrant/test_catalog_index.py backend/tests/adapters/qdrant/test_catalog_search.py -v
uv run --project backend pytest backend/tests/features/catalog/use_cases/test_index_price_items.py -v
```

## Phase 3: `search_items` Backend Tool

**Outcome:** Backend can search catalog items semantically, run minimal keyword fallback, apply simple filters, hydrate rows from Postgres and return checkable item cards suitable for assistant/UI.

**Files:**

- Create: `backend/app/features/catalog/dto.py`
- Create: `backend/app/features/catalog/use_cases/search_price_items.py`
- Modify: `backend/app/entrypoints/http/catalog.py`
- Modify: `backend/app/entrypoints/http/schemas/catalog.py`
- Modify: `backend/app/entrypoints/http/dependencies.py`
- Modify: `docs/api/openapi.yaml`
- Modify: `docs/agent/search.md`

**Steps:**

- [ ] Write failing use case tests for query embedding with `catalog_query_prefix`, Qdrant search, Postgres hydration and semantic ranking preservation.
- [ ] Write failing tests for filters: `supplier_city`, `category`, `supplier_status`, `has_vat`, `unit_price`.
- [ ] Write failing keyword fallback tests:
  - query by supplier name such as `ООО НИКА`;
  - query by `supplier_inn`;
  - query by exact service/model words in `name`;
  - query by exact text in `source_text`;
  - query by `external_id`.
- [ ] Write failing tests for semantic + keyword merge without duplicate `price_item_id` results.
- [ ] Write failing tests for backend-generated `match_reason` codes and `source_text_snippet`.
- [ ] Write failing tests for empty Qdrant/keyword results returning an empty item list.
- [ ] Write failing HTTP tests for `POST /catalog/search`.
- [ ] Add catalog search DTOs.
- [ ] Implement `SearchPriceItemsUseCase`.
- [ ] Add tool-friendly `search_items` service contract.
- [ ] Add `POST /catalog/search`.
- [ ] Update OpenAPI and search docs.
- [ ] Run focused catalog search checks.

**Verification:**

```bash
uv run --project backend pytest backend/tests/features/catalog/use_cases/test_search_price_items.py -v
uv run --project backend pytest backend/tests/entrypoints/http/test_catalog.py -v
```

## Phase 4: Unified Chat API With Router And Brief State

**Outcome:** `POST /assistant/chat` routes user messages, updates one active brief state and calls `search_items` when useful. Assistant prose explains and guides, while `found_items` remains the checkable evidence for catalog search.

**Files:**

- Create: `backend/app/features/assistant/dto.py`
- Create: `backend/app/features/assistant/ports.py`
- Create: `backend/app/features/assistant/brief.py`
- Create: `backend/app/features/assistant/router.py`
- Create: `backend/app/features/assistant/use_cases/chat_turn.py`
- Create: `backend/app/entrypoints/http/assistant.py`
- Create: `backend/app/entrypoints/http/schemas/assistant.py`
- Modify: `backend/app/entrypoints/http/router.py`
- Modify: `backend/app/entrypoints/http/dependencies.py`
- Modify: `docs/api/openapi.yaml`
- Modify: `docs/agent/search.md`

**Steps:**

- [ ] Write failing brief merge tests for null values, arrays, overwritten scalar fields, `venue_status`, `duration_or_time_window` and `event_level`.
- [ ] Write failing router tests:
  - `Хочу музыкальный вечер` -> `brief_discovery`;
  - `Нужно музыкальное оборудование в концертный зал` -> `supplier_search`;
  - `Организовать музыкальный вечер на 100 человек, помоги понять что нужно` -> `mixed`.
- [ ] Write failing chat turn tests for `brief_discovery` without search.
- [ ] Write failing chat turn tests for `supplier_search` with `search_items`.
- [ ] Write failing chat turn tests for `mixed` with brief update plus search.
- [ ] Write failing chat turn tests that `supplier_search` returns `found_items`, not only prose like "я нашел варианты".
- [ ] Write failing chat turn tests that `mixed` updates `brief` and returns cards when `should_search_now=true`.
- [ ] Write failing assistant response tests that `message` does not introduce prices, suppliers, phones, emails, INNs or date availability unless backed by `found_items`.
- [ ] Write failing empty-result tests where the assistant says the catalog has no matching rows and suggests refinement.
- [ ] Write failing HTTP tests for `POST /assistant/chat`.
- [ ] Add assistant DTOs and ports.
- [ ] Implement deterministic brief merge.
- [ ] Implement structured router adapter/helper.
- [ ] Implement `ChatTurnUseCase`.
- [ ] Ensure `ChatTurnUseCase` returns four separate response layers: `message`, `router`, `brief`, `found_items`.
- [ ] Ensure `found_items` are treated as candidates, not selected budget/proposal lines.
- [ ] Add assistant HTTP endpoint.
- [ ] Wire dependencies without cross-feature imports.
- [ ] Update OpenAPI and search docs.
- [ ] Run focused assistant checks.

**Verification:**

```bash
uv run --project backend pytest backend/tests/features/assistant/test_brief.py -v
uv run --project backend pytest backend/tests/features/assistant/test_router.py -v
uv run --project backend pytest backend/tests/features/assistant/use_cases/test_chat_turn.py -v
uv run --project backend pytest backend/tests/entrypoints/http/test_assistant.py -v
```

## Phase 5: Frontend Unified Chat, Brief Draft And Found Items

**Outcome:** The first user screen is one assistant workspace with chat, brief draft and found catalog item cards/table. Catalog admin/list/detail remains available separately.

**Files:**

- Modify: `frontend/src/api.ts`
- Create: `frontend/src/pages/AssistantPage.tsx`
- Create: `frontend/src/components/AssistantChat.tsx`
- Create: `frontend/src/components/BriefDraftPanel.tsx`
- Create: `frontend/src/components/FoundItemsPanel.tsx`
- Modify: `frontend/src/pages/CatalogPage.tsx`
- Create: `frontend/src/pages/CatalogItemPage.tsx`
- Modify: `frontend/src/pages/Home.tsx`
- Modify: `frontend/src/pages/SearchPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.css`

**Steps:**

- [ ] Add TypeScript DTOs for `BriefState`, `RouterDecision`, `FoundItem`, catalog item list/detail and assistant chat response.
- [ ] Add API functions for `/assistant/chat`, `/catalog/items`, `/catalog/items/{id}` and `/catalog/search`.
- [ ] Build `AssistantChat` with message thread and composer.
- [ ] Build `BriefDraftPanel` with compact current brief fields.
- [ ] Build `FoundItemsPanel` with `name`, `unit_price`, `unit`, `supplier`, `supplier_city`, `category`, `source_text_snippet` and backend-generated `match_reason`.
- [ ] Build `AssistantPage` as the primary user workspace.
- [ ] Keep assistant prose visually separate from "Черновик брифа" and "Найденные позиции".
- [ ] Ensure catalog facts are visible in cards/table and are not only embedded in assistant text.
- [ ] Update catalog page into a data/admin table for imported rows.
- [ ] Add catalog item detail route that shows full `source_text` and CSV provenance.
- [ ] Remove primary search/brief tabs from the user flow.
- [ ] Preserve existing document routes and drill-down navigation.
- [ ] Run frontend build.

**Verification:**

```bash
cd frontend
npm run build
```

Manual checks:

- [ ] Message `Хочу музыкальный вечер` updates brief, gives a live explanation and asks clarifying questions without inventing catalog facts.
- [ ] Message `Нужно музыкальное оборудование в концертный зал` shows preliminary found items when indexed rows exist.
- [ ] Mixed scenario `Хочу организовать музыкальный вечер на 100 человек, помоги понять что нужно` produces live explanation, updates brief draft and shows checkable catalog cards when search runs.
- [ ] Search result facts are visible in "Найденные позиции" rather than only inside the chat text.
- [ ] Found item opens `/catalog/items/:id`.
- [ ] Catalog item detail shows full source text/provenance for verification.
- [ ] Existing document upload/status/search pages remain reachable.

## Phase 6: Post-MVP PDF Ingestion Adaptation

**Outcome:** PDF ingestion can optionally extract catalog-compatible rows after the CSV/search/chat baseline is stable.

**Files:**

- Modify: `packages/sage/sage/models.py`
- Modify: `packages/sage/sage/llm/prompts.py`
- Modify: `packages/sage/sage/llm/extract.py`
- Modify: `packages/sage/sage/process.py`
- Create: `backend/app/features/catalog/use_cases/upsert_document_price_items.py`
- Create: `backend/app/features/catalog/use_cases/link_document_price_items.py`
- Modify: `backend/app/features/ingest/use_cases/process_document.py`
- Modify: `backend/app/features/contractors/use_cases/resolve_contractor.py`
- Modify: `backend/app/features/ingest/use_cases/index_document.py`
- Modify: `backend/app/entrypoints/celery/composition.py`
- Modify: `backend/app/entrypoints/celery/tasks/ingest.py`
- Modify: `docs/agent/pipeline.md`
- Modify: `docs/agent/data-model.md`

**Steps:**

- [ ] Add SAGE tests for `PriceItemExtraction` and `ProcessingResult.price_items`.
- [ ] Add SAGE tests for parsing `{contract_fields, price_items}`.
- [ ] Add backend tests for storing document-derived catalog candidates.
- [ ] Add backend tests for linking document-derived rows after contractor resolution.
- [ ] Add backend tests for indexing document-derived catalog rows through the same `IndexPriceItemsUseCase`.
- [ ] Add regression tests that a document with no extracted price items can still become `INDEXED`.
- [ ] Add `PriceItemExtraction` to SAGE.
- [ ] Update prompt and parser for catalog-compatible extraction.
- [ ] Store document-derived rows using catalog normalization and `prices_v1`.
- [ ] Link rows after contractor resolution.
- [ ] Index rows into `price_items_search_v1`.
- [ ] Preserve document lifecycle and task names.
- [ ] Update pipeline/data-model docs.
- [ ] Run SAGE and backend ingestion checks.

**Verification:**

```bash
uv run --project packages/sage pytest packages/sage/tests/test_models.py packages/sage/tests/test_llm.py packages/sage/tests/test_process.py -v
uv run --project backend pytest backend/tests/features/ingest/use_cases/test_process_document.py -v
uv run --project backend pytest backend/tests/features/contractors/use_cases/test_resolve_contractor.py -v
uv run --project backend pytest backend/tests/features/ingest/use_cases/test_index_document.py -v
```

## Phase 7: Post-MVP Search Quality And Commercial Workflow

**Outcome:** Improve quality and workflows only after the main catalog assistant works end to end.

**Workstreams:**

- Legacy embeddings auxiliary layer:
  - duplicate detection inside old CSV imports;
  - similar-to-existing-row using legacy vectors from the same vector space;
  - clustering and import QA;
  - evaluation against new `prices_v1` embeddings.
- Dedupe/merge UI:
  - candidate duplicate groups;
  - manual accept/reject;
  - source preservation.
- Hybrid search:
  - Postgres full-text/trigram tuning or Qdrant sparse+dense only after evaluation data exists;
  - ranking metrics such as precision@k, MRR or NDCG.
- Selected item workflow:
  - `selected_item_ids`;
  - "Добавить в подборку";
  - budget summary based on selected rows, not every candidate in `found_items`.
- Document RAG:
  - separate document answer flow;
  - cite document chunks/summaries as secondary evidence;
  - do not replace catalog cards/table with prose summaries.
- Commercial proposal generation:
  - selected item set;
  - budget summary;
  - export-ready proposal only after search and brief state are reliable.

## Completion Criteria For MVP

- `prices.csv` imports into `price_items`.
- Repeated exact CSV rows do not create duplicate active search results.
- Every valid item has deterministic `embedding_text` with `prices_v1`.
- Primary vectors are generated by the configured catalog embedding model with `search_document:` prefix.
- Generated vectors are stored in Qdrant, not Postgres.
- `catalog_index_status` distinguishes `indexed`, `embedding_failed` and `indexing_failed`.
- Qdrant collection `price_items_search_v1` contains indexed active catalog rows.
- `search_items` returns hydrated Postgres item cards with semantic search, minimal keyword fallback and simple filters.
- `search_items` returns `source_text_snippet` and backend-generated `match_reason`.
- `POST /assistant/chat` supports `brief_discovery`, `supplier_search`, `mixed` and `clarification`.
- Frontend first screen is a unified assistant workspace, not search/brief tabs.
- Assistant response keeps `message`, `brief` and `found_items` as separate layers.
- Found items show `name`, `unit_price`, `unit`, `supplier`, `supplier_city`, `category`, `source_text_snippet` and `match_reason`.
- Prices, suppliers, cities, units and sources shown in assistant-facing search are backed by `price_items`.
- CSV legacy embeddings are not used in user search.
- Existing PDF upload/status/document drill-down search remains available.
