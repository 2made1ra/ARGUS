# Phase Execution Prompts

Готовые промпты для выполнения фаз из
[`05-phased-execution.md`](05-phased-execution.md). Используй один промпт на
одну сессию/ветку/PR, если не указано иначе.

Промпты составлены по принципам OpenAI Prompt Guidance:

- начинать с желаемого результата, а не с длинной инструкции по каждому шагу;
- явно задавать границы, источники контекста и критерии успеха;
- включать правила проверки, стоп-условия и формат финального ответа;
- держать этапы разделенными, чтобы агент не перескакивал к следующей фазе;
- просить короткие рабочие обновления перед существенными tool/file actions.

Источник: <https://developers.openai.com/api/docs/guides/prompt-guidance>

## Как использовать

1. Передай агенту один промпт из нужной фазы.
2. Не вставляй весь `05-phased-execution.md`: он уже является источником
   задачи внутри репозитория.
3. Для Phase 1-5 работай в implementation/default режиме после принятия
   задачи.
4. Для Phase 6-7 сначала включай plan/review режим, потому что это post-MVP
   работа и она зависит от стабильности CSV/search/chat baseline.
5. Не проси агента переходить к следующей фазе в той же сессии, если текущая
   фаза не завершена и не проверена.

## Общие правила для всех фаз

Добавляй этот блок к фазовому промпту, если агент не видит текущих
репозиторных инструкций:

```text
Перед началом прочитай CLAUDE.md, AGENTS.md и только релевантные docs/agent/*
для этой фазы. Следуй catalog-first MVP направлению:

- prices.csv populates price_items.
- Postgres price_items is the source of truth for catalog facts.
- Qdrant price_items_search_v1 is the controlled catalog vector index.
- New embeddings come from deterministic embedding_text prices_v1.
- CSV legacy embedding is audit-only and is never used for user query search.
- Unified assistant chat response separates message, router, brief, found_items.
- Primary catalog search result is checkable Postgres item cards/table, not RAG prose.
- Existing PDF/document workflow remains available unless the current phase explicitly changes it.

Architecture rule:
- Business logic belongs in use cases/domain services, never routes/adapters.
- Features do not import each other directly; use explicit contracts and shared core types.
- Routes, Celery tasks and adapters stay thin.

Workflow:
- Work only inside the requested phase.
- Use TDD for behavior changes: write failing tests first, then implementation.
- If the phase plan conflicts with current code, stop and explain the conflict before broad edits.
- Do not run destructive commands.
- Do not commit, push or open a PR unless asked separately.
- In the final response, list changed files and verification commands with results.
```

## Phase 1 Prompt: `price_items` Persistence And CSV Import

```text
Выполни Phase 1 из docs/plans/catalog-first-refactor/05-phased-execution.md:
price_items persistence and CSV import.

Goal:
prices.csv can be imported into Postgres as raw import rows plus normalized
active price_items. Legacy CSV embeddings are preserved only as audit metadata.
Repeated exact rows must not inflate active search results.

Read first:
- CLAUDE.md
- AGENTS.md
- docs/agent/architecture.md
- docs/agent/data-model.md
- docs/agent/dev.md
- docs/plans/catalog-first-refactor/01-data-model-and-csv-import.md
- docs/plans/catalog-first-refactor/04-embeddings-and-qdrant.md
- docs/plans/catalog-first-refactor/05-phased-execution.md

Scope:
- Work only on Phase 1 files and tests.
- Add the catalog persistence/import layer, ORM models, migration, repositories,
  use cases and catalog HTTP endpoints required by Phase 1.
- Update docs/api/openapi.yaml and docs/agent/data-model.md only as required by
  Phase 1.
- Do not implement Qdrant indexing, search_items, assistant chat or frontend UI.
- Do not alter the existing PDF/document lifecycle.

Required behavior:
- Parse prices.csv with csv.DictReader, including multiline source_text.
- Store raw price_import_rows and normalized price_items.
- Preserve CSV legacy embedding only as audit metadata such as present/dim/raw
  import information; never make it the primary vector.
- Generate deterministic embedding_text using prices_v1.
- Make source_text inclusion deterministic:
  empty source_text omitted; "Ручной ввод" omitted; source_text equal to name
  after normalization omitted; meaningful description included.
- Add row_fingerprint and repeated import protection so exact repeated rows do
  not create duplicate active search cards.
- Keep business logic in catalog use cases/domain services, not routes/adapters.

Testing:
- Start with failing tests from the Phase 1 checklist.
- Include CSV parser tests, normalization tests, embedding_text snapshot tests,
  import use case tests, duplicate-protection tests, repository tests and HTTP
  endpoint tests.

Verification to run:
uv run --project backend pytest backend/tests/features/catalog/test_csv_parser.py -v
uv run --project backend pytest backend/tests/features/catalog/test_normalization.py -v
uv run --project backend pytest backend/tests/features/catalog/test_embedding_text.py -v
uv run --project backend pytest backend/tests/features/catalog/use_cases/test_import_prices_csv.py -v
uv run --project backend pytest backend/tests/adapters/sqlalchemy/test_price_items.py -v
uv run --project backend pytest backend/tests/entrypoints/http/test_catalog.py -v

Stop conditions:
- Stop if existing schema or repository structure makes the planned migration
  unsafe or ambiguous.
- Stop if implementing Phase 1 requires changing PDF task chaining or document
  Qdrant payloads.
- Stop after Phase 1 verification. Do not start Phase 2.

Final response:
- Summarize changed files by layer.
- Report each verification command and result.
- Call out any skipped checks or infrastructure blockers.
```

## Phase 2 Prompt: Catalog Indexing Into `price_items_search_v1`

```text
Выполни Phase 2 из docs/plans/catalog-first-refactor/05-phased-execution.md:
catalog indexing into price_items_search_v1.

Goal:
Valid active catalog rows are embedded with the configured catalog embedding
model and indexed into Qdrant collection price_items_search_v1. Generated vectors
live only in Qdrant unless a later explicit design adds vector persistence.

Read first:
- CLAUDE.md
- AGENTS.md
- docs/agent/architecture.md
- docs/agent/data-model.md
- docs/agent/search.md
- docs/agent/dev.md
- docs/plans/catalog-first-refactor/04-embeddings-and-qdrant.md
- docs/plans/catalog-first-refactor/05-phased-execution.md

Scope:
- Work only on Phase 2 files and tests.
- Implement catalog embedding/indexing config, Qdrant bootstrap, Qdrant index
  adapter, Qdrant catalog search adapter mapping and IndexPriceItemsUseCase.
- Do not implement search_items API ranking/merge behavior from Phase 3.
- Do not implement assistant chat or frontend UI.
- Do not modify document chunk collection semantics.

Required behavior:
- Do not infer catalog embedding dimension from CSV legacy embeddings.
- Do not use CSV legacy embedding as the catalog vector.
- Do not mix document_chunks vectors and price_items vectors in one Qdrant collection.
- Split document and catalog embedding/vector config.
- For nomic-embed-text-v1.5, document-side catalog item embedding input must be:
  catalog_document_prefix + embedding_text, where default prefix is "search_document: ".
- Query prefix config must also exist for Phase 3, default "search_query: ".
- Prefer one generate+index MVP flow:
  embedding_text -> embedding generation -> dimension validation -> Qdrant upsert
  -> catalog_index_status update.
- Distinguish embedding generation failure from Qdrant indexing failure:
  embedding_failed and indexing_failed must be observable separately with
  separate errors.
- Generated vectors are stored in Qdrant, not Postgres.

Testing:
- Start with failing tests from the Phase 2 checklist.
- Include tests proving legacy embeddings are ignored, prefix is applied,
  catalog dimension is explicit, payload indexes are bootstrapped and status
  transitions distinguish embedding_failed from indexing_failed.

Verification to run:
uv run --project backend pytest backend/tests/test_config.py backend/tests/adapters/qdrant/test_bootstrap.py -v
uv run --project backend pytest backend/tests/adapters/qdrant/test_catalog_index.py backend/tests/adapters/qdrant/test_catalog_search.py -v
uv run --project backend pytest backend/tests/features/catalog/use_cases/test_index_price_items.py -v

Stop conditions:
- Stop if current embedding adapter cannot support separate document/catalog
  config without a broader design decision.
- Stop if Qdrant bootstrap changes would affect existing document search
  collection behavior.
- Stop after Phase 2 verification. Do not start Phase 3.

Final response:
- Summarize changed files by layer.
- Report each verification command and result.
- Explicitly state where generated vectors are stored and how failures are separated.
```

## Phase 3 Prompt: `search_items` Backend Tool

```text
Выполни Phase 3 из docs/plans/catalog-first-refactor/05-phased-execution.md:
search_items backend tool.

Goal:
Backend can search catalog items semantically, run minimal keyword fallback,
apply simple filters, hydrate rows from Postgres and return checkable item cards
for assistant/UI. The primary search result is found_items, not prose.

Read first:
- CLAUDE.md
- AGENTS.md
- docs/agent/architecture.md
- docs/agent/data-model.md
- docs/agent/search.md
- docs/agent/dev.md
- docs/plans/catalog-first-refactor/03-search-and-ui.md
- docs/plans/catalog-first-refactor/04-embeddings-and-qdrant.md
- docs/plans/catalog-first-refactor/05-phased-execution.md

Scope:
- Work only on Phase 3 files and tests.
- Implement SearchPriceItemsUseCase, DTOs, tool-friendly search_items service
  contract and POST /catalog/search.
- Update docs/api/openapi.yaml and docs/agent/search.md as required by Phase 3.
- Do not implement assistant chat routing from Phase 4.
- Do not implement frontend UI from Phase 5.
- Do not turn document RAG into the catalog search result.

Required behavior:
- Query embedding input uses catalog_query_prefix + user search query, default
  prefix "search_query: ".
- Qdrant semantic search uses price_items_search_v1 only.
- Hydrate returned IDs from Postgres price_items; Postgres remains source of truth.
- Support simple filters: supplier_city, category, supplier_status, has_vat,
  unit_price.
- Add minimal keyword fallback using Postgres keyword/ILIKE/full-text style
  search for supplier name, supplier_inn, exact words in name/source_text and
  external_id.
- Merge semantic and keyword results without duplicate price_item_id rows.
- Return source_text_snippet and backend-generated match_reason.
- match_reason must be safe/template-based; do not ask the LLM to invent it.
- Empty semantic and keyword results return an empty list, not fabricated cards.

Testing:
- Start with failing tests from the Phase 3 checklist.
- Include semantic search, query prefix, hydration, filters, keyword fallback,
  merge de-duplication, match_reason/source_text_snippet and empty-result tests.

Verification to run:
uv run --project backend pytest backend/tests/features/catalog/use_cases/test_search_price_items.py -v
uv run --project backend pytest backend/tests/entrypoints/http/test_catalog.py -v

Stop conditions:
- Stop if existing Qdrant adapter cannot provide stable IDs/scores without a
  design change.
- Stop if implementing keyword fallback requires a new external search service.
- Stop after Phase 3 verification. Do not start Phase 4.

Final response:
- Summarize changed files by layer.
- Report each verification command and result.
- Include the final found_items/card fields returned by search_items.
```

## Phase 4 Prompt: Unified Chat API With Router And Brief State

```text
Выполни Phase 4 из docs/plans/catalog-first-refactor/05-phased-execution.md:
unified chat API with router and brief state.

Goal:
POST /assistant/chat routes user messages, updates one active brief state and
calls search_items when useful. Assistant prose explains and guides, while
found_items remains the checkable evidence for catalog search.

Read first:
- CLAUDE.md
- AGENTS.md
- docs/agent/architecture.md
- docs/agent/data-model.md
- docs/agent/search.md
- docs/agent/dev.md
- docs/plans/catalog-first-refactor/03-search-and-ui.md
- docs/plans/catalog-first-refactor/05-phased-execution.md

Scope:
- Work only on Phase 4 files and tests.
- Implement assistant DTOs, ports, brief merge, router helper/adapter,
  ChatTurnUseCase and POST /assistant/chat.
- Update docs/api/openapi.yaml and docs/agent/search.md as required by Phase 4.
- Do not implement frontend UI from Phase 5.
- Do not generate final commercial proposals.
- Do not use document RAG as the main answer for catalog search.

Required behavior:
- Router intents: brief_discovery, supplier_search, mixed, clarification.
- Chat response has four separate layers:
  message, router, brief, found_items.
- message is a human explanation, not the source of truth for catalog facts.
- found_items is the only place for concrete found catalog rows.
- Prices, suppliers, phones, emails, INNs, units, cities and date availability
  must not appear as claims in message unless backed by found_items or an opened
  catalog item detail.
- supplier_search returns found_items, not only prose like "я нашел варианты".
- mixed updates brief and returns cards when should_search_now=true.
- Empty result says the catalog has no matching rows and suggests refinement.
- found_items are candidates, not selected budget/proposal lines.
- Keep assistant feature decoupled from catalog internals through explicit
  ports/service contracts.

Testing:
- Start with failing tests from the Phase 4 checklist.
- Include brief merge tests, router intent tests, chat turn tests for each
  intent, unsupported prose-only search tests, evidence-backed message tests and
  HTTP tests.

Verification to run:
uv run --project backend pytest backend/tests/features/assistant/test_brief.py -v
uv run --project backend pytest backend/tests/features/assistant/test_router.py -v
uv run --project backend pytest backend/tests/features/assistant/use_cases/test_chat_turn.py -v
uv run --project backend pytest backend/tests/entrypoints/http/test_assistant.py -v

Stop conditions:
- Stop if assistant implementation would require direct cross-feature imports
  instead of explicit contracts.
- Stop if current OpenAPI/client contracts make the response layering ambiguous.
- Stop after Phase 4 verification. Do not start Phase 5.

Final response:
- Summarize changed files by layer.
- Report each verification command and result.
- Show a compact example of the final /assistant/chat response shape.
```

## Phase 5 Prompt: Frontend Unified Chat, Brief Draft And Found Items

```text
Выполни Phase 5 из docs/plans/catalog-first-refactor/05-phased-execution.md:
frontend unified chat, brief draft and found items.

Goal:
The first user screen becomes one assistant workspace with chat, brief draft and
found catalog item cards/table. Catalog admin/list/detail remains available
separately. Existing document upload/status/search routes remain reachable.

Read first:
- CLAUDE.md
- AGENTS.md
- docs/agent/architecture.md
- docs/agent/search.md
- docs/agent/dev.md
- docs/api/openapi.yaml
- docs/plans/catalog-first-refactor/03-search-and-ui.md
- docs/plans/catalog-first-refactor/05-phased-execution.md

Scope:
- Work only on Phase 5 frontend files and tests/build checks.
- Implement TypeScript DTOs, API functions, AssistantPage, AssistantChat,
  BriefDraftPanel, FoundItemsPanel, CatalogItemPage and route updates required
  by Phase 5.
- Preserve existing document routes and drill-down navigation.
- Do not change backend behavior unless the build reveals a strict type/API
  mismatch that cannot be handled in frontend code. If that happens, stop and
  explain before editing backend.
- Do not replace found item cards/table with prose.

Required UX behavior:
- Assistant prose is visually separate from "Черновик брифа" and
  "Найденные позиции".
- Found item facts are visible as cards/table with:
  name, unit_price, unit, supplier, supplier_city, category,
  source_text_snippet and backend-generated match_reason.
- Catalog item detail route shows full source_text and CSV provenance.
- The primary user flow no longer asks users to choose between search and brief
  tabs.
- Document upload/status/search pages remain available.

Design constraints:
- Build the actual usable workspace as the first screen, not a landing page.
- Keep operational UI dense, readable and stable across desktop/mobile widths.
- Do not put catalog facts only inside chat text.
- Use existing app conventions and styling before inventing a new design system.

Verification to run:
cd frontend
npm run build

Manual checks:
- "Хочу музыкальный вечер" updates brief, gives explanation and asks questions
  without inventing catalog facts.
- "Нужно музыкальное оборудование в концертный зал" shows preliminary found
  items when indexed rows exist.
- "Хочу организовать музыкальный вечер на 100 человек, помоги понять что нужно"
  produces explanation, updates brief draft and shows checkable catalog cards
  when search runs.
- Search result facts are visible in "Найденные позиции".
- Found item opens /catalog/items/:id.
- Catalog detail shows full source_text/provenance.
- Existing document upload/status/search pages remain reachable.

Stop conditions:
- Stop if backend endpoints from earlier phases are missing or incompatible.
- Stop if preserving document routes conflicts with the new primary route design.
- Stop after Phase 5 build/manual checks. Do not start Phase 6.

Final response:
- Summarize changed files by UI area.
- Report build result and manual checks completed or blocked.
- Include any API mismatch that needs a backend follow-up.
```

## Phase 6 Prompt: Post-MVP PDF Ingestion Adaptation

```text
Plan and execute Phase 6 from
docs/plans/catalog-first-refactor/05-phased-execution.md only after confirming
that Phase 1-5 CSV/search/chat baseline is stable.

Goal:
PDF ingestion can optionally extract catalog-compatible rows after the baseline
catalog assistant works. The existing PDF lifecycle remains unchanged:
QUEUED -> PROCESSING -> RESOLVING -> INDEXING -> INDEXED.

First action:
Before editing, verify whether Phase 1-5 are implemented and passing. If the
baseline is not present, stop and report that Phase 6 is premature.

Read first:
- CLAUDE.md
- AGENTS.md
- docs/agent/architecture.md
- docs/agent/pipeline.md
- docs/agent/data-model.md
- docs/agent/search.md
- docs/plans/catalog-first-refactor/02-document-ingestion-to-catalog.md
- docs/plans/catalog-first-refactor/05-phased-execution.md

Scope:
- Work only on Phase 6 files and tests.
- Add optional PDF-to-catalog extraction that produces catalog-compatible
  candidates, then stores/indexes them through the same catalog contract as CSV.
- Preserve document upload, processing, contractor resolution, indexing task
  names and lifecycle semantics.
- Do not make document chunks the primary evidence for catalog search.
- Do not replace catalog item cards/table with document RAG summaries.

Required behavior:
- Add PriceItemExtraction to SAGE only as a structured optional output.
- Parsing should handle {contract_fields, price_items}.
- Document-derived rows use catalog normalization and prices_v1 embedding_text.
- Document-derived rows index through IndexPriceItemsUseCase into
  price_items_search_v1.
- A document with no extracted price items can still become INDEXED.
- Existing document search/RAG remains a secondary flow.

Testing:
- Start with failing tests from the Phase 6 checklist.
- Include SAGE model/parser/process tests, backend storage/linking tests,
  indexing-through-catalog tests and no-price-items regression tests.

Verification to run:
uv run --project packages/sage pytest packages/sage/tests/test_models.py packages/sage/tests/test_llm.py packages/sage/tests/test_process.py -v
uv run --project backend pytest backend/tests/features/ingest/use_cases/test_process_document.py -v
uv run --project backend pytest backend/tests/features/contractors/use_cases/test_resolve_contractor.py -v
uv run --project backend pytest backend/tests/features/ingest/use_cases/test_index_document.py -v

Stop conditions:
- Stop if Phase 1-5 are not implemented or not stable.
- Stop if optional catalog extraction would require changing document lifecycle
  or task chaining.
- Stop if SAGE prompt/parser changes would make contract field extraction invent
  missing facts.
- Stop after Phase 6 verification. Do not start Phase 7.

Final response:
- Summarize changed files by SAGE/backend/docs layer.
- Report baseline check, verification commands and results.
- Explicitly state that PDF lifecycle and document RAG/search remained available.
```

## Phase 7 Prompt: Post-MVP Search Quality And Commercial Workflow

```text
Work on Phase 7 from docs/plans/catalog-first-refactor/05-phased-execution.md.
This is post-MVP work. Do not implement all workstreams at once.

Goal:
Improve quality and commercial workflows only after the main catalog assistant
works end to end. Choose exactly one Phase 7 workstream per session unless the
user explicitly asks for a larger project.

First action:
Review Phase 1-5 completion criteria and confirm the catalog assistant baseline:
CSV import, indexing, search_items, assistant chat and frontend workspace. If
the baseline is missing, stop and recommend returning to the earliest incomplete
phase.

Choose one workstream:
- legacy embeddings auxiliary layer;
- dedupe/merge UI;
- hybrid search quality;
- selected item workflow;
- document RAG secondary flow;
- commercial proposal generation.

Read first:
- CLAUDE.md
- AGENTS.md
- docs/agent/architecture.md
- docs/agent/data-model.md
- docs/agent/search.md
- docs/agent/pipeline.md when touching document RAG
- docs/plans/catalog-first-refactor/05-phased-execution.md
- the plan/doc most relevant to the selected workstream

Scope:
- Before code edits, produce a short implementation plan for the selected
  workstream: affected files, tests, data migration risk, rollback/disable path
  and acceptance criteria.
- Wait for user approval if the workstream changes data model, ranking behavior,
  proposal generation or document RAG behavior.
- Do not mix multiple Phase 7 workstreams in one PR unless explicitly asked.

Non-negotiable boundaries:
- Legacy embeddings remain auxiliary. Do not use user query embeddings against
  legacy CSV vectors.
- Hybrid search changes need evaluation data and metrics such as precision@k,
  MRR or NDCG.
- selected_item_ids represent chosen rows; found_items remain search candidates.
- Budget summaries and proposals must be based on selected rows, not every
  candidate returned by search.
- Document RAG is separate secondary evidence and must not replace catalog
  cards/table.

Testing and verification:
- Define focused tests before implementation.
- Include regression tests that catalog cards remain primary evidence.
- Run workstream-specific backend/frontend/SAGE checks and any relevant build.

Stop conditions:
- Stop if the baseline catalog assistant is incomplete.
- Stop if the chosen workstream needs product decisions not covered by the plan.
- Stop if implementation would merge multiple workstreams without explicit
  approval.

Final response:
- State which workstream was chosen.
- Summarize changed files and behavior.
- Report verification commands and results.
- List remaining Phase 7 workstreams still untouched.
```

## Optional Prompt: MVP Completion Audit

```text
Проверь готовность MVP по Completion Criteria из
docs/plans/catalog-first-refactor/05-phased-execution.md.

Goal:
Produce an evidence-based audit of catalog-first MVP readiness without making
code changes.

Read first:
- CLAUDE.md
- AGENTS.md
- docs/agent/*
- docs/plans/catalog-first-refactor/05-phased-execution.md

Scope:
- Inspect code, tests, routes, schemas, migrations and docs.
- Do not edit files.
- Do not run destructive commands.

Output:
- Checklist table: criterion, status, evidence file/test, gap.
- Earliest incomplete phase.
- Recommended next prompt to execute.
- Risks around PDF lifecycle, legacy embeddings and RAG replacing catalog cards.
```
