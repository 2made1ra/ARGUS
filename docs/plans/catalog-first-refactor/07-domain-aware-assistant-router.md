# Domain-Aware Assistant Router Implementation Plan

> **For agentic workers:** If available, use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. If those sub-skills are unavailable, execute the plan phase-by-phase with the focused tests listed under each phase. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the MVP assistant router into a domain-aware event-manager interpreter that can update the event brief, plan catalog searches, use LLM assistance for routing now, and keep catalog facts evidence-backed.

**Architecture:** Keep `assistant` as a vertical slice that owns chat behavior, brief state, routing, search planning, response composition and tool orchestration. Catalog facts still come only from `price_items` through explicit catalog ports; LLM output is allowed for structured interpretation, not for supplier, price, city, phone, email, INN or availability facts.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2 HTTP schemas, dataclass domain DTOs, LM Studio through the existing OpenAI-compatible LLM adapter, PostgreSQL `price_items`, Qdrant `price_items_search_v1`, pytest.

---

## Current Baseline

Backend already has the MVP assistant slice:

- `backend/app/features/assistant/dto.py` defines `BriefState`, `RouterDecision`, `FoundCatalogItem` and chat request/response DTOs.
- `backend/app/features/assistant/router.py` contains `HeuristicAssistantRouter`, which currently routes by simple patterns and returns one `search_query`.
- `backend/app/features/assistant/use_cases/chat_turn.py` merges the brief and calls `CatalogSearchTool.search_items()` once when `should_search_now` is true.
- `backend/app/features/catalog/use_cases/search_price_items.py` already provides semantic Qdrant search, Postgres hydration, backend `match_reason` and minimal keyword fallback.
- `docs/plans/catalog-first-refactor/05-phased-execution.md` currently treats the assistant router as an MVP phase; this plan is the next backend evolution, not a replacement for the completed MVP.

## Non-Negotiable Guardrails

- `message` is not source of truth for catalog facts.
- `found_items` and item detail rows from Postgres are the only source of truth for item names, prices, units, suppliers, cities, contacts, INNs and availability-like claims.
- Router and LLM-router must return structured JSON/DTO only; they must not generate the final assistant message.
- `ResponseComposer` owns user-facing prose and must not invent catalog facts.
- `ChatTurnUseCase` orchestrates use cases and tools; FastAPI routes remain thin.
- Assistant feature code must not import catalog internals directly. It calls catalog through ports/adapters wired in HTTP dependencies.
- CSV legacy `embedding` remains audit-only and must not be used for user query search.
- Raw `test_files/prices.csv` can be used as an import fixture/evaluation source, but production search must run over imported `price_items`, not raw CSV files.

## Target Backend Flow

```text
POST /assistant/chat
  -> ChatTurnUseCase
      -> load active BriefState from request/session context
      -> normalize message
      -> extract deterministic event-domain signals
      -> call LLMStructuredEventRouter for structured routing assistance
      -> validate, merge and repair/fallback router DTO
      -> merge brief patch
      -> build SearchPlan from search_requests
      -> call backend tools:
           update_brief
           search_items
           get_item_details
           select_item / compare_items later
      -> compose safe assistant message
      -> return message + router + brief + found_items
```

The first implementation should use active `BriefState` as required context and `recent_turns` as optional context. Do not introduce a database-backed chat history in this phase unless the task explicitly expands to persistence; the frontend can send recent turns, and tests can pass them directly.

Selection and comparison also need explicit visible candidate context from the UI. The router must not infer ordinal references such as `второй вариант` from stale server memory unless the request provides `visible_candidates` or the item is already in `selected_item_ids`.

## Target DTO Contract

### `BriefState` v2

Replace the single `budget` field with explicit budget semantics while preserving migration/backward compatibility in HTTP schemas during rollout:

```json
{
  "event_type": null,
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
  "required_services": [],
  "selected_item_ids": [],
  "constraints": [],
  "preferences": [],
  "open_questions": []
}
```

Implementation notes:

- Keep `venue_constraints` separate from general `constraints` because phrases such as `площадка без подвеса` affect lighting, staging and rigging searches.
- Keep `budget_total` and `budget_per_guest` separate because `до 2500 на гостя` is not the same fact as `2 млн общий бюджет`.
- Preserve backward compatibility while rolling out HTTP schemas: legacy numeric `budget` maps to `budget_total`, legacy string `budget` maps to `budget_notes`, and v2 responses prefer `budget_total`, `budget_per_guest` and `budget_notes`.
- `selected_item_ids` are not the same as `found_items`; found items are candidates, selected items are explicit user choices.
- `open_questions` is assistant state for unresolved high-value questions, not a substitute for router `clarification_questions`.

### `RouterDecision` v2

```json
{
  "intent": "mixed",
  "confidence": 0.84,
  "reason_codes": [
    "brief_update_detected",
    "service_need_detected",
    "search_action_detected"
  ],
  "brief_update": {},
  "search_requests": [],
  "should_search_now": true,
  "missing_fields": [],
  "clarification_questions": [],
  "user_visible_summary": null
}
```

Allowed intents:

```text
brief_discovery | supplier_search | mixed | clarification | selection | comparison
```

`search_query` should be deprecated in favor of `search_requests[]`. During migration, the HTTP response may include both `search_query` and `search_requests`; backend orchestration must use `search_requests`.

Reason codes must include deterministic and LLM merge/fallback outcomes such as `brief_update_detected`, `service_need_detected`, `search_action_detected`, `llm_router_fallback_used` and `llm_conflict_resolved`.

### `SearchRequest`

```json
{
  "query": "фермы сценические конструкции ground support без подвеса Екатеринбург",
  "service_category": "сценические конструкции",
  "filters": {
    "supplier_city_normalized": "екатеринбург",
    "category": null,
    "supplier_status_normalized": null,
    "has_vat": null,
    "vat_mode": null,
    "unit_price_min": null,
    "unit_price_max": null
  },
  "priority": 1,
  "limit": 8
}
```

Search requests are router/search-planner instructions, not catalog facts. The `service_category` value is used for grouping, query construction and UI labels; it does not assert that a found Postgres row belongs to that category unless the hydrated row says so.

`SearchRequest.filters` must be a typed `CatalogSearchFilters`, not a free-form `dict`. Supported fields:

- `supplier_city_normalized: str | None`
- `category: str | None`
- `supplier_status_normalized: str | None`
- `has_vat: bool | None`
- `vat_mode: str | None`
- `unit_price_min: Decimal | None`
- `unit_price_max: Decimal | None`

Unknown filter keys from an LLM response or HTTP request are dropped during schema validation and never reach catalog search.

### `visible_candidates`

`POST /assistant/chat` may include the currently visible item ordinals so selection and comparison can resolve user references deterministically:

```json
[
  {"ordinal": 1, "item_id": "price-item-uuid-a"},
  {"ordinal": 2, "item_id": "price-item-uuid-b"}
]
```

The mapping is request context, not durable state. If a selection or comparison message refers to an ordinal and `visible_candidates` is absent or cannot resolve the ordinal, the router returns `clarification`, asks which item the user means, and does not mutate `selected_item_ids`.

## File Map

### Create

- `backend/app/features/assistant/domain/taxonomy.py` - event service categories, aliases, city aliases and action vocabulary.
- `backend/app/features/assistant/domain/slot_extraction.py` - deterministic extraction of event slots from a message.
- `backend/app/features/assistant/domain/action_detection.py` - deterministic detection of search, brief update, selection, comparison and contextual actions.
- `backend/app/features/assistant/domain/search_planning.py` - converts router `search_requests` into executable catalog search operations.
- `backend/app/features/assistant/domain/response_composer.py` - safe prose generation from router decision, brief before/after, search status and found items.
- `backend/app/features/assistant/domain/llm_router.py` - structured LLM-router prompt building, JSON validation and fallback handling.
- `backend/app/adapters/llm/assistant_router.py` - LM Studio/OpenAI-compatible adapter that implements the assistant LLM router port.
- `backend/tests/fixtures/assistant_router_cases.json` - golden router/evaluation dataset.
- `backend/tests/features/assistant/test_event_taxonomy.py`
- `backend/tests/features/assistant/test_slot_extraction.py`
- `backend/tests/features/assistant/test_action_detection.py`
- `backend/tests/features/assistant/test_router_context.py`
- `backend/tests/features/assistant/test_router_golden_cases.py`
- `backend/tests/features/assistant/test_search_planning.py`
- `backend/tests/features/assistant/test_response_composer.py`

### Modify

- `backend/app/features/assistant/dto.py` - add `BriefPatch`, `CatalogSearchFilters`, `SearchRequest`, `SearchPlan`, `ChatTurn`, `VisibleCandidate`, `RouterDecision` v2 fields and new intents.
- `backend/app/features/assistant/brief.py` - merge new brief fields and selected item ids without duplicating list values.
- `backend/app/features/assistant/ports.py` - update `AssistantRouter.route()` to accept `recent_turns` and `visible_candidates`; add ports for LLM structured routing, catalog details and selection/comparison tools when implemented.
- `backend/app/features/assistant/router.py` - replace single heuristic router with rule-based domain interpreter plus LLM-assisted structured router behind the same port.
- `backend/app/features/assistant/use_cases/chat_turn.py` - orchestrate router, brief merge, search planner, backend tools and response composer.
- `backend/app/entrypoints/http/schemas/assistant.py` - expose `BriefState` v2, typed `search_requests.filters`, `visible_candidates`, `reason_codes`, `clarification_questions` and optional `recent_turns`.
- `backend/app/entrypoints/http/dependencies.py` - wire LLM router adapter, search planner dependencies and catalog tool adapters.
- `docs/api/openapi.yaml` - update assistant request/response contract after backend DTOs are stable.
- `docs/agent/search.md` - document domain-aware router v2 and evidence rules.
- `docs/plans/catalog-first-refactor/05-phased-execution.md` - only after implementation starts, mark this work as the next backend phase instead of editing completed checkboxes opportunistically.

### Review Existing

- `backend/app/features/catalog/use_cases/search_price_items.py`
- `backend/app/adapters/sqlalchemy/price_items.py`
- `backend/tests/features/catalog/use_cases/test_search_price_items.py`
- `test_files/prices.csv`

These files already cover part of keyword fallback. The new work should audit and strengthen them rather than duplicate catalog search logic in assistant.

## Phase 0: Seed Router Golden Dataset

**Outcome:** Router behavior has a small golden evaluation set before deterministic or LLM router implementation starts.

Create `backend/tests/fixtures/assistant_router_cases.json` with 25-40 high-signal event-manager cases. This dataset is the rollout gate for Phase A and Phase B: deterministic extractors and LLM-router merge/fallback behavior must be developed against these cases before any UI-facing router behavior changes.

Golden case shape:

```json
{
  "message": "добавь, что площадка без подвеса, и посмотри фермы",
  "brief_before": {
    "event_type": "конференция",
    "city": "Москва",
    "audience_size": 300
  },
  "recent_turns": [],
  "visible_candidates": [],
  "expected_intent": "mixed",
  "expected_should_search_now": true,
  "expected_brief_update": {
    "venue_constraints": ["площадка без подвеса"],
    "required_services": ["фермы"]
  },
  "expected_service_categories": [
    "сценические конструкции",
    "свет"
  ],
  "expected_missing_fields": [],
  "expected_reason_codes": []
}
```

Seed groups:

- [ ] Pure brief updates.
- [ ] Pure catalog searches.
- [ ] Mixed brief update plus search.
- [ ] Contextual phrases: `под это`, `тогда`, `в Екате`, `на это количество`.
- [ ] Venue constraints.
- [ ] Budget total, budget per guest and legacy `budget` compatibility.
- [ ] Urgency and availability-like preferences.
- [ ] Geography and city aliases.
- [ ] Service categories and bundles.
- [ ] Empty, vague and unsafe messages.
- [ ] Selection and comparison with `visible_candidates`.
- [ ] Selection and comparison without `visible_candidates`, expecting clarification and no `selected_item_ids` mutation.

Minimum seed phrases:

```text
а что есть по свету на 300 гостей?
надо закрыть welcome-зону
в Екате кто сможет быстро?
добавь, что площадка без подвеса, и посмотри фермы
Бюджет около 2 млн, город Екатеринбург
На 120 человек в Екатеринбурге нужен кейтеринг до 2500 на гостя
Ок, тогда найди сцену и свет под это
Площадка уже есть, монтаж только ночью
Нужен звук, но без премиума, что-то рабочее
Добавь в подборку второй вариант
Сравни первые два по цене
```

Evaluation assertions:

- intent accuracy;
- `should_search_now` accuracy;
- slot extraction correctness;
- legacy and v2 budget mapping correctness;
- brief patch correctness;
- service category detection;
- search request count, priorities and typed filters;
- missing field detection;
- clarification question quality;
- selection/comparison behavior with and without visible candidates.

Focused check:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_router_golden_cases.py -v
```

## Phase A: Domain Taxonomy And Deterministic Extractors

**Outcome:** Assistant can understand common event-manager language before involving an LLM.

- [ ] Add service taxonomy for `звук`, `свет`, `сценические конструкции`, `мультимедиа`, `кейтеринг`, `welcome-зона`, `персонал`, `логистика`, `декор`, `мебель`, `площадка`.
- [ ] Add aliases such as `радики -> радиомикрофоны`, `Екат -> Екатеринбург`, `фермы -> сценические конструкции`, `экран -> мультимедиа`.
- [ ] Add action vocabulary:
  - search: `найди`, `подбери`, `покажи варианты`, `есть ли`, `кто сможет`, `нужно закрыть`;
  - brief update: `добавь`, `запомни`, `город будет`, `бюджет`, `площадка`;
  - selection: `берем`, `добавь в подборку`, `второй вариант`;
  - comparison: `сравни`, `что дешевле`, `первые два`;
  - contextual: `под это`, `тогда`, `в этом городе`, `на это количество`.
- [ ] Extract slots:
  - `event_type`;
  - `city`;
  - `date_or_period`;
  - `audience_size`;
  - `venue_status`;
  - `venue_constraints`;
  - `duration_or_time_window`;
  - `event_level`;
  - `budget_total`;
  - `budget_per_guest`;
  - `budget_notes`;
  - `required_services`;
  - `constraints`;
  - `preferences`.
- [ ] Keep deterministic extractors side-effect-free and unit-testable.

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_event_taxonomy.py -v
uv run --project backend pytest backend/tests/features/assistant/test_slot_extraction.py -v
uv run --project backend pytest backend/tests/features/assistant/test_action_detection.py -v
```

Required examples:

- `Екат` -> `Екатеринбург`.
- `300 гостей` -> `audience_size=300`.
- `до 2500 на гостя` -> `budget_per_guest=2500`.
- `около 2 млн` -> `budget_total=2000000`.
- legacy numeric `budget` -> `budget_total`; legacy string `budget` -> `budget_notes`.
- `без подвеса` -> `venue_constraints=["площадка без подвеса"]`.
- `свет/звук/фермы/welcome` -> normalized service categories.

## Phase B: LLM-Assisted Structured Router Now

**Outcome:** Router uses LLM help for messy event-manager phrases while deterministic extraction and fallback keep behavior reproducible.

Architecture:

```text
RuleBasedEventInterpreter
  -> deterministic slots/actions/categories/context hints
  -> LLMStructuredEventRouterPort
      -> adapters/llm/assistant_router.py performs LM Studio/OpenAI-compatible call
      -> strict JSON RouterDecision v2
      -> validation, merge and repair
      -> fallback to deterministic RouterDecision or clarification when invalid/low confidence
```

- [ ] Keep `AssistantRouter` as the stable port:

```python
class AssistantRouter(Protocol):
    async def route(
        self,
        *,
        message: str,
        brief: BriefState,
        recent_turns: list[ChatTurn],
        visible_candidates: list[VisibleCandidate],
    ) -> RouterDecision: ...
```

- [ ] Add `LLMStructuredRouterPort` in assistant ports; implement it in `backend/app/adapters/llm/assistant_router.py` and wire it from `entrypoints/http/dependencies.py`.
- [ ] Keep `backend/app/features/assistant/domain/llm_router.py` limited to prompt construction, schema definitions, validation, repair, merge policy and fallback decisions.
- [ ] Keep all network calls in `backend/app/adapters/llm/assistant_router.py`; domain code must not call LM Studio, OpenAI-compatible clients or any external service directly.
- [ ] Use existing LM Studio/OpenAI-compatible configuration; do not add a new external service or dependency without explicit approval.
- [ ] Prompt the LLM with:
  - normalized user message;
  - active `BriefState`;
  - recent turns;
  - visible candidate ordinal-to-item mapping;
  - deterministic extracted slots/actions/categories;
  - allowed intents;
  - allowed reason codes;
  - strict JSON schema.
- [ ] Validate all LLM output against domain DTOs.
- [ ] Clamp confidence to `0.0..1.0`.
- [ ] Drop unknown fields and unknown enum values.
- [ ] Merge from deterministic first, LLM second: deterministic extracted facts always win for `brief_update`, `selected_item_ids` and typed filters.
- [ ] Allow LLM output to enrich `search_requests`, `clarification_questions`, `missing_fields` and `user_visible_summary` when it does not conflict with deterministic facts.
- [ ] If LLM output conflicts with deterministic extraction, keep the deterministic value, drop the conflicting LLM value and add reason code `llm_conflict_resolved`.
- [ ] If JSON is invalid or unsafe, use deterministic fallback and add reason code `llm_router_fallback_used`.
- [ ] If validated LLM confidence is `<0.55`, fall back to deterministic routing; if deterministic routing cannot safely infer intent, return `clarification` with 1-3 questions.
- [ ] LLM-router must not call tools, search catalog, generate final prose or invent catalog facts.
- [ ] Unit tests must use a fake LLM adapter with fixed responses; real LM Studio calls are integration tests only and must be marked/skipped outside integration runs.
- [ ] Add tests for valid LLM JSON, malformed JSON, unsupported intent, low confidence, conflicting LLM facts, unsafe invented catalog facts and deterministic fallback.

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_router_context.py -v
uv run --project backend pytest backend/tests/features/assistant/test_router_golden_cases.py -v
```

## Phase C: Router Decision Logic

**Outcome:** Intent is decided from the interpreted working situation, not from raw message keywords.

Decision rules:

- `brief_discovery`: only brief facts or planning context were provided; no immediate service need.
- `supplier_search`: service need/search action exists; brief patch may be empty.
- `mixed`: both brief patch and service search need exist.
- `clarification`: no safe service need and insufficient context.
- `selection`: user refers to one or more existing found/selected item candidates that can be resolved through `visible_candidates` or explicit item ids.
- `comparison`: user asks to compare known candidates or selected items that can be resolved through `visible_candidates`, explicit item ids or existing `selected_item_ids`.
- Ordinal references such as `первый`, `второй`, `первые два` require `visible_candidates`; if absent or incomplete, return `clarification` and do not mutate `selected_item_ids`.

Required behavior:

- [ ] `а что есть по свету на 300 гостей?` -> `mixed`, update `audience_size`, add `required_services=["свет"]`, search now.
- [ ] `надо закрыть welcome-зону` -> `supplier_search` or `mixed`, expand to welcome/personnel/decor search requests.
- [ ] `в Екате кто сможет быстро?` with active service context -> `supplier_search`; empty context -> `clarification`.
- [ ] `добавь, что площадка без подвеса, и посмотри фермы` -> `mixed`, update `venue_constraints`, search scenics/ground support and light stands.
- [ ] `Бюджет около 2 млн, город Екатеринбург` -> `brief_discovery`, no search.
- [ ] `На 120 человек в Екатеринбурге нужен кейтеринг до 2500 на гостя` -> `mixed`, budget per guest, city, audience, catering search.
- [ ] `Ок, тогда найди сцену и свет под это` with active brief -> `supplier_search` using brief context.
- [ ] `Добавь в подборку второй вариант` with `visible_candidates[2]` -> `selection`, no catalog search, append the resolved item id once.
- [ ] `Добавь в подборку второй вариант` without visible candidate context -> `clarification`, no catalog search, no `selected_item_ids` mutation.
- [ ] `Сравни первые два по цене` with visible candidates -> `comparison`, no catalog search, compare hydrated item fields only.

## Phase D: Search Planner And Multi-Search Orchestration

**Outcome:** Assistant can run one or several controlled catalog searches from `search_requests[]`.

- [ ] Add `SearchPlanner` that accepts `RouterDecision`, `BriefState` before/after and returns ordered executable searches.
- [ ] Use `priority` and a backend cap. Initial cap: execute up to 3 searches per chat turn.
- [ ] Apply typed `CatalogSearchFilters` from brief and search request, especially `supplier_city_normalized`, `category`, `supplier_status_normalized`, `has_vat`, `vat_mode`, `unit_price_min` and `unit_price_max`.
- [ ] Generate richer query text with event context, audience size, venue constraints and budget preference when useful.
- [ ] Preserve flat `found_items` for API compatibility, and add grouping markers when the API is updated: `result_group`, `matched_service_category` and `matched_service_categories[]`.
- [ ] Merge multi-search results by sorting planned groups by `priority`, then sorting each group by backend score.
- [ ] Deduplicate found items by `id` across multiple searches. Keep the first group's `result_group` and `matched_service_category`, and append every matched category to `matched_service_categories[]` when the same item appears in multiple searches.
- [ ] Keep `search_items` as the catalog tool; do not duplicate semantic/keyword search logic in assistant.

Examples:

```text
User: нужен звук и экран на корпоратив 180 человек в Тюмени

SearchPlan:
1. звуковое оборудование акустика микрофоны корпоратив 180 человек Тюмень
2. экран проектор led экран мультимедиа корпоратив 180 человек Тюмень
```

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_search_planning.py -v
uv run --project backend pytest backend/tests/features/assistant/use_cases/test_chat_turn.py -v
```

## Phase E: Backend Tools

**Outcome:** Chat orchestration uses explicit backend tools instead of ad hoc logic.

Minimum tools for this phase:

- [ ] `update_brief`: merge `BriefPatch` into `BriefState` with deterministic list dedupe and scalar overwrite rules.
- [ ] `search_items`: execute one planned catalog search through the existing catalog use case, with filters and limit.
- [ ] `get_item_details`: open one catalog item detail through the existing catalog detail use case.

Next tools after router v2 is stable:

- [ ] `select_item`: add explicit user-selected item ids to `BriefState.selected_item_ids`.
- [ ] `compare_items`: compare selected/found item rows by real hydrated fields only.
- [ ] `render_event_brief`: render a human brief from `BriefState`, without catalog price claims.
- [ ] `estimate_budget_from_selected_items`: compute rough budget only from selected rows and explicit quantities.

Implementation boundaries:

- Tools are Python services/use cases called by `ChatTurnUseCase`.
- Tools are not free-form agent skills and do not execute arbitrary actions.
- Tool results are structured DTOs.
- Any tool that returns catalog facts must return hydrated Postgres data or explicit errors.
- `select_item` may mutate `selected_item_ids` only after a visible ordinal or explicit item id resolves to a known candidate; unresolved ordinal references must return clarification instead of guessing.

## Phase F: ResponseComposer

**Outcome:** Assistant speaks naturally while staying within evidence rules.

- [ ] Move `_message_for()` out of `ChatTurnUseCase` into `ResponseComposer`.
- [ ] MVP `ResponseComposer` uses deterministic safe templates only.
- [ ] Optional LLM paraphrasing is post-MVP or must be hidden behind a separate response-paraphrasing port with the same evidence rules.
- [ ] Inputs:
  - router decision;
  - brief before;
  - brief after;
  - planned searches;
  - search status: `ran | skipped | empty | failed`;
  - found item count/group summaries;
  - catalog limitations.
- [ ] Never include item-specific price, supplier, phone, email, INN, city, contact or availability facts in `message`, even when those facts are present in `found_items`.
- [ ] Mention brief changes in human language.
- [ ] Mention that found items are candidates when search ran.
- [ ] If no search ran, explain why.
- [ ] If results are empty, say the catalog has no matching rows and suggest refinements.
- [ ] Ask 1-3 clarification questions, not 5, unless the UI has a separate checklist.

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_response_composer.py -v
```

## Phase G: Minimal Keyword Fallback Based On `prices.csv`

**Outcome:** Short professional queries work even when semantic embeddings are weak.

The current catalog search already has keyword fallback over imported Postgres rows. This phase strengthens it with regression data from `test_files/prices.csv`.

- [ ] Import `test_files/prices.csv` in an integration-style fixture or reuse existing import tests to create representative `price_items`.
- [ ] Build regression cases from actual CSV columns:
  - `id` -> `external_id`;
  - `name`;
  - `source_text`;
  - `section`;
  - `category`;
  - `supplier`;
  - `supplier_inn`;
  - `supplier_city`;
  - `has_vat`;
  - `supplier_status`.
- [ ] Add queries for exact supplier names, INNs, city aliases, professional abbreviations, VAT phrases, status phrases, category/section words and short equipment/service words.
- [ ] Ensure keyword fallback reads from imported `price_items`; do not query raw CSV at runtime.
- [ ] Keep first implementation simple: normalized exact match plus `ILIKE`/case-insensitive containment over `name`, `source_text`, `supplier`, `supplier_inn` and `external_id`.
- [ ] Include simple fallback/filter parsing for `has_vat`, `vat_mode`, `category`, `section`, `supplier_city` and `supplier_status` so examples such as `Без НДС` are testable and not just free-text queries.
- [ ] Add regression tests for `section`, `category`, `supplier_city`, VAT and status filters when the imported CSV has representative values.
- [ ] Do not implement full hybrid ranking yet. Sparse vectors, RRF, trigram tuning and Postgres full-text ranking remain post-evaluation improvements.

Required keyword regression examples:

```text
ООО НИКА
7701234567
радиомикрофон
фермы
Екат
Без НДС
external_id from prices.csv
meaningful fragment from source_text
```

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/catalog/use_cases/test_search_price_items.py -v
uv run --project backend pytest backend/tests/adapters/sqlalchemy/test_price_items.py -v
```

## Phase H: Expand Router Evaluation Dataset

**Outcome:** The Phase 0 seed dataset grows into a broad regression suite after the core router behavior is stable.

- [ ] Expand `backend/tests/fixtures/assistant_router_cases.json` from 25-40 seed cases to 100-150 cases as real phrases appear.
- [ ] Preserve the Phase 0 groups and add more cases for multi-search ranking, typed filters, LLM conflict resolution, low-confidence fallback, legacy budget mapping and visible candidate selection/comparison.
- [ ] Keep `test_router_golden_cases.py` as a unit/CI test with deterministic or fake LLM behavior only.
- [ ] Add real LM Studio evaluation only as a separately marked integration test; it must not be required for unit or CI runs.

Focused check:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_router_golden_cases.py -v
```

## Phase I: API And Frontend Compatibility

**Outcome:** New router fields are visible to the UI without collapsing evidence layers.

- [ ] Update `docs/api/openapi.yaml` after backend schemas are implemented.
- [ ] Keep response layers as `message`, `router`, `brief`, `found_items`.
- [ ] Add `router.search_requests[]`, `router.reason_codes[]`, `router.clarification_questions[]`.
- [ ] Add typed `CatalogSearchFilters` schema under `router.search_requests[].filters`; unknown filter keys are not part of the OpenAPI contract.
- [ ] Add optional request `visible_candidates[]` with `ordinal` and `item_id` for selection/comparison turns.
- [ ] Add v2 brief fields to frontend DTOs only after backend response is stable.
- [ ] Preserve legacy request `brief.budget` during rollout: numeric values map to `budget_total`, string values map to `budget_notes`.
- [ ] Prefer v2 response fields `budget_total`, `budget_per_guest` and `budget_notes`; include legacy `budget` only while required for compatibility.
- [ ] Keep `found_items` cards/table checkable and visually separate from assistant prose.
- [ ] If grouped search results are implemented, either:
  - add `result_group`, `matched_service_category` and `matched_service_categories[]` on each item, or
  - add a separate `found_item_groups` response field after OpenAPI review.

## Rollout Order

1. Seed the 25-40 case golden router dataset and make `test_router_golden_cases.py` runnable before router behavior changes.
2. Land DTO additions, typed `CatalogSearchFilters`, visible candidate request context and deterministic extractors behind tests.
3. Run the seed dataset against deterministic behavior before implementing LLM router behavior.
4. Add LLM structured router with strict validation, deterministic-first merge, conflict handling and low-confidence fallback.
5. Add `search_requests[]` and `SearchPlanner` while keeping old `search_query` compatibility.
6. Move prose to deterministic safe-template `ResponseComposer`.
7. Expand keyword fallback regression coverage using imported `test_files/prices.csv`.
8. Grow the golden router dataset after behavior is stable.
9. Update OpenAPI and frontend DTOs after backend tests pass.
10. Remove old single-query routing paths only after the frontend no longer depends on `search_query`.

## Acceptance Criteria

- Router classifies the event-manager working situation, not just message keywords.
- Router receives `message`, active `BriefState`, optional `recent_turns` and optional `visible_candidates`.
- LLM-router is used for structured routing assistance now, with deterministic-first merge, `llm_conflict_resolved` on conflicts and deterministic/clarification fallback below confidence `0.55`.
- Router returns `reason_codes`, `brief_update`, `search_requests[]`, `should_search_now`, `missing_fields` and `clarification_questions`.
- `SearchRequest.filters` uses typed `CatalogSearchFilters`; unknown filter keys are dropped.
- Selection/comparison only uses visible candidate ordinal-to-item mappings or explicit selected ids; absent context asks clarification and does not mutate `selected_item_ids`.
- `ChatTurnUseCase` can execute multiple planned searches with a backend cap.
- Multi-search results preserve `result_group`, `matched_service_category` and `matched_service_categories[]`, sort by group priority then score, and dedupe by item id.
- Backend tools are explicit services/use cases, not arbitrary agent actions.
- `ResponseComposer` uses deterministic safe templates and produces natural Russian responses without item-specific catalog facts in `message`.
- Minimal keyword fallback works for short professional queries, exact CSV-derived identifiers and simple VAT/category/section/city/status filter parsing after importing `prices.csv`.
- Legacy request `budget` maps into v2 budget fields, and v2 responses prefer `budget_total`, `budget_per_guest` and `budget_notes`.
- Evaluation dataset exists and can be run in CI/unit test mode without Postgres, Redis, Qdrant, LibreOffice, Tesseract or LM Studio unless explicitly marked integration.

## Verification Commands

Run focused tests first:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_event_taxonomy.py -v
uv run --project backend pytest backend/tests/features/assistant/test_slot_extraction.py -v
uv run --project backend pytest backend/tests/features/assistant/test_action_detection.py -v
uv run --project backend pytest backend/tests/features/assistant/test_router_context.py -v
uv run --project backend pytest backend/tests/features/assistant/test_router_golden_cases.py -v
uv run --project backend pytest backend/tests/features/assistant/test_search_planning.py -v
uv run --project backend pytest backend/tests/features/assistant/test_response_composer.py -v
uv run --project backend pytest backend/tests/features/assistant/use_cases/test_chat_turn.py -v
uv run --project backend pytest backend/tests/features/catalog/use_cases/test_search_price_items.py -v
```

Then broaden:

```bash
uv run --project backend pytest backend/tests/features/assistant backend/tests/features/catalog/use_cases/test_search_price_items.py -v
uv run --project backend pytest backend/tests/entrypoints/http/test_assistant.py backend/tests/entrypoints/http/test_catalog.py -v
```

If OpenAPI/frontend DTOs change:

```bash
cd frontend
npm run build
```
