# Event Brief Assistant Orchestrator Implementation Plan

> **For agentic workers:** If available, use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. If those sub-skills are unavailable, execute the plan phase-by-phase with the focused tests listed under each phase. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the MVP `chat -> heuristic router -> one search` flow with a controlled assistant orchestrator that supports two UX modes: an event-brief workspace when the user is creating or planning an event, and a chat-only catalog search flow when the user is simply looking for a contractor or service. Both modes use catalog-backed evidence and must not invent supplier facts.

**Architecture:** ARGUS assistant is not a free-running agent. One user turn enters `ChatTurnUseCase`, an `EventBriefInterpreter` produces structured interpretation with deterministic extraction plus LLM assistance, backend policy validates the decision, a bounded tool executor calls only approved backend tools, and `ResponseComposer` builds the user-facing message from structured state and evidence-backed results.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, dataclass/domain DTOs, LM Studio through the existing OpenAI-compatible LLM adapter, PostgreSQL `price_items`, Qdrant `price_items_search_v1`, pytest.

**Product UX companion:** This document is the backend implementation plan. The target end-to-end UX and scenario acceptance criteria live in `docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md`.

---

## Current Baseline

Backend already has the MVP assistant slice:

- `backend/app/features/assistant/dto.py` defines the current `BriefState`, `RouterDecision`, `FoundCatalogItem` and chat request/response DTOs.
- `backend/app/features/assistant/router.py` contains `HeuristicAssistantRouter`, which routes by simple patterns and regular expressions.
- `backend/app/features/assistant/ports.py` lets the router see only `message` and `brief`.
- `backend/app/features/assistant/use_cases/chat_turn.py` merges the brief and calls `CatalogSearchTool.search_items()` once when `should_search_now` is true.
- `backend/app/features/catalog/use_cases/search_price_items.py` already provides semantic Qdrant search, Postgres hydration, backend `match_reason` and minimal keyword fallback.
- `docs/agent/entity-resolution.md` says CSV supplier fields stay on `price_items`; they are not automatically resolved into `contractors`.

This is enough for MVP routing, but not enough for the target workflows:

```text
event request -> brief collection -> service planning -> catalog search
  -> supplier verification -> final event brief

direct contractor/service search -> clarification -> catalog candidates in chat
```

## Non-Negotiable Guardrails

- `price_items` in Postgres remains the source of truth for catalog facts.
- Qdrant `price_items_search_v1` is the controlled vector index for catalog search.
- CSV legacy `embedding` remains audit-only and must not be used for user query search.
- `message` is not the source of truth for prices, suppliers, INNs, cities, contacts, units, statuses or availability-like claims.
- `found_items`, opened item details and supplier verification tool results are the only sources for catalog and supplier facts.
- LLM output is allowed only for structured interpretation. It must not call tools, write final prose, generate SQL, perform HTTP requests, or invent catalog facts.
- Core behavior must pass with deterministic extraction and fake LLM responses. Real LM Studio calls are optional integration checks and must not block the first end-to-end slice.
- `ChatTurnUseCase` orchestrates domain/application services. FastAPI routes and adapters stay thin.
- Assistant feature code must not import catalog internals directly. It calls catalog through ports/adapters wired in HTTP dependencies.
- One chat turn is bounded: initial defaults should be `max_tool_calls_per_turn=3`, `max_llm_retries=1`, and no recursive autonomous loop.
- Backend tools are explicit Python services/use cases, not free-form agent skills.

## Target UX Modes

The assistant must choose the visible UX mode from the interpreted situation:

```text
brief_workspace
  User explicitly creates, prepares, plans or organizes an event.
  UI shows chat + draft brief + grouped candidates + verification + final brief.

chat_search
  User only asks to find a contractor, supplier, item, price or service.
  UI stays as a simple chat. Clarifying questions and catalog result cards are rendered inside the chat timeline.
```

The brief interface must not appear just because a message mentions an event domain term. It appears when the user intent is about creating, preparing or managing an event brief:

```text
Нужно организовать корпоратив на 120 человек в Екатеринбурге
Собери бриф на конференцию
Готовим презентацию продукта, нужна площадка и подрядчики
```

The chat-only search flow remains active for direct search requests:

```text
Найди подрядчика по свету в Екатеринбурге
Есть кто по кейтерингу до 2500 на гостя?
Покажи радиомикрофоны у поставщиков с НДС
```

The backend should expose this as structured state, not as a frontend guess.

## Target Backend Flow

```text
POST /assistant/chat
  -> ChatTurnUseCase
      -> load active BriefState from request/session context
      -> read optional recent_turns, visible_candidates and candidate_item_ids
      -> EventBriefInterpreter
          -> deterministic slot extraction
          -> deterministic action/service/category detection
          -> LLM structured routing assistance
          -> schema validation, deterministic-first merge, fallback
          -> Interpretation
      -> BriefWorkflowPolicy
          -> decide interface_mode
          -> decide workflow_stage
          -> decide missing fields and open questions
          -> decide whether search, verification or render is allowed now
          -> ActionPlan
      -> ToolExecutor
          -> update_brief
          -> search_items
          -> get_item_details
          -> verify_supplier_status
          -> render_event_brief
          -> ToolResults
      -> ResponseComposer
          -> safe user-facing message
      -> ChatTurnResponse
      -> return message + ui_mode + router + action_plan + brief + found_items + verification_results + rendered_brief
```

The first implementation can continue receiving `BriefState` from the request. Do not introduce database-backed chat history in this plan unless a later task explicitly expands persistence. `recent_turns` and `visible_candidates` are request context.

## State And Context Assumptions

The first implementation is stateless on the backend side except for `BriefState` and explicit UI context passed by the client. The backend must not resolve phrases such as `найденных`, `второй вариант`, `первые два` or `эти подрядчики` from hidden server memory.

Request context should include:

```json
{
  "recent_turns": [],
  "visible_candidates": [
    {
      "ordinal": 1,
      "item_id": "uuid",
      "service_category": "кейтеринг"
    }
  ],
  "candidate_item_ids": ["uuid-1", "uuid-2"]
}
```

Rules:

- Selection and comparison can resolve ordinal references only through `visible_candidates`.
- `Проверь найденных подрядчиков` can target only `BriefState.selected_item_ids`, request `candidate_item_ids`, request `visible_candidates`, or explicit item ids in the message.
- If no candidate context exists, verification returns a clarification action and no `verification_results`.
- Persisted chat history can be added later, but this plan must not silently depend on it.

## Minimum Valuable Slices

This plan is a roadmap, not one large PR. Implement it in small slices that each preserve the existing MVP.

### MVS-1: Event Brief Core

Build the smallest useful event-brief flow:

- `BriefState` v2 compatibility fields;
- `workflow_stage`;
- deterministic slot extraction;
- missing-field policy;
- `ResponseComposer` with 1-3 questions;
- deterministic/fake LLM only;
- `manual_not_verified` supplier verification adapter only;
- deterministic brief renderer skeleton only.

No real LLM dependency, no full supplier verification, no frontend redesign.

### MVS-2: Service Planning And Search Groups

Add catalog value without expanding agency behavior:

- service taxonomy;
- `SearchRequest[]`;
- grouped or tagged `found_items`;
- request `visible_candidates`;
- request `candidate_item_ids`;
- `max 3` searches per turn.

### MVS-3: Verification, Render And LLM Enrichment

Complete the event workflow after the core path is stable:

- supplier verification target resolution;
- INN dedupe for verification;
- final `render_event_brief`;
- structured LLM interpreter as enrichment, not as the source of workflow authority.

## Target Domain Model

### DTO Separation

Do not let one router DTO decide facts, policy and tools at the same time. The orchestrator should pass through four explicit layers:

```text
EventBriefInterpreter
  -> Interpretation
     extracted facts, raw intent, brief_update, service needs, action signals,
     references to visible candidates and confidence/reason codes

BriefWorkflowPolicy
  -> ActionPlan
     interface_mode, workflow_stage, allowed tool intents, search_requests,
     verification_targets, render_requested and clarification_questions

ToolExecutor
  -> ToolResults
     found_items, item_details, verification_results, rendered_brief and
     skipped tool reasons

ResponseComposer
  -> ChatTurnResponse
     message, ui_mode, router/action diagnostics, brief and evidence payloads
```

`RouterDecision` can remain as a public compatibility/debug section in the response, but it must be assembled from `Interpretation + ActionPlan`. It is not the object that authorizes tool execution.

### `BriefState` v2

The brief becomes the center of the product workflow:

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

Implementation notes:

- Keep `concept`, `event_goal` and `format`; mentor feedback explicitly calls out concept as part of a real event brief.
- Keep `venue_constraints` separate from general `constraints` because `площадка без подвеса` changes lighting, staging, rigging and multimedia planning.
- Keep `budget_total`, `budget_per_guest` and `budget_notes` separate. `до 2500 на гостя` is not the same as `2 млн общий бюджет`.
- Preserve request compatibility while rolling out: legacy numeric `budget` maps to `budget_total`; legacy string `budget` maps to `budget_notes`; v2 responses prefer explicit budget fields.
- `found_items` are candidates; `selected_item_ids` are explicit user choices.
- `open_questions` is state for unresolved high-value fields, not a substitute for turn-level `clarification_questions`.

Service field semantics:

- `service_needs` is the normalized model used by policy and search planning.
- `required_services` is a compatibility/UI projection of explicitly requested service blocks.
- `must_have_services` contains explicitly mandatory blocks only.
- `nice_to_have_services` contains policy suggestions and must never be treated as selected or mandatory.
- `technical_requirements` contains execution requirements, not service categories.
- `venue_constraints` contains constraints caused by the venue only.
- `constraints` is reserved for non-venue business constraints.
- `preferences` is soft guidance such as `без премиума` or `быстро`.

Normalized service need shape:

```json
{
  "category": "свет",
  "priority": "nice_to_have",
  "source": "policy_inferred",
  "reason": "площадка без подвеса",
  "notes": "искать стойки, напольные приборы или ground support"
}
```

### `EventBriefWorkflowState`

Add a workflow stage separate from raw intent:

```text
intake
clarifying
service_planning
supplier_searching
supplier_verification
brief_ready
brief_rendered
```

The same intent can mean different actions in different stages. For example, `mixed` during intake may update the brief and ask questions, while `mixed` during service planning may update venue constraints and run targeted searches.

Transition matrix:

| Current stage | User signal | Required facts | Next stage | Allowed tools |
| --- | --- | --- | --- | --- |
| `intake` | describes event | event type, city or audience can be partial | `clarifying` | `update_brief` |
| `clarifying` | provides date, budget, venue or concept | enough facts for planning, not necessarily complete | `service_planning` | `update_brief` |
| `service_planning` | says `подбери`, `найди`, `посмотри` | service category or policy-inferred service need | `supplier_searching` | `search_items` |
| `supplier_searching` | says `добавь второй` | `visible_candidates` contains ordinal and item id | `supplier_searching` | `select_item` |
| `supplier_searching` | says `проверь найденных подрядчиков` | selected ids, candidate ids, visible candidates or explicit item ids | `supplier_verification` | `verify_supplier_status` |
| `supplier_verification` | says `сформируй бриф` | non-empty brief exists | `brief_rendered` | `render_event_brief` |

Service inference is not the same as catalog search. For example, `площадка без подвеса` can add `nice_to_have` service needs for ground support and floor lighting, but policy must not call `search_items` unless the user asks to search or the workflow is already in a search step.

### `AssistantInterfaceMode`

Add a UI mode separate from workflow stage:

```text
brief_workspace
chat_search
```

Selection rules:

- `brief_workspace` is selected when the user explicitly says they are creating, organizing, planning, preparing or assembling an event, or asks to build/render a brief.
- `brief_workspace` is preserved once a non-empty event brief is active and the user continues with contextual phrases such as `под это`, `тогда`, `добавь в бриф`, or `сформируй итоговый бриф`.
- `chat_search` is selected when the user asks only for a contractor, supplier, service, catalog item, price row or comparison without asking to create an event or maintain a brief.
- `chat_search` may still keep an ephemeral search context for follow-up clarification, but it must not force the full brief panel open.
- If the request is ambiguous, default to `chat_search` and ask whether the user wants to start an event brief.

### `Interpretation`

`Interpretation` is the interpreter output. It contains what the user said and what the message appears to request, but it does not authorize tools.

```json
{
  "interface_mode": "brief_workspace",
  "intent": "mixed",
  "confidence": 0.84,
  "reason_codes": [
    "brief_update_detected",
    "service_need_detected",
    "search_action_detected"
  ],
  "brief_update": {},
  "service_needs": [],
  "requested_actions": ["update_brief", "search_items"],
  "candidate_references": [],
  "missing_fields": [],
  "clarification_questions": [],
  "user_visible_summary": null
}
```

Allowed intents:

```text
brief_discovery | supplier_search | mixed | clarification | selection | comparison | verification | render_brief
```

Reason codes should include deterministic and LLM merge/fallback outcomes:

```text
brief_update_detected
service_need_detected
service_bundle_detected
search_action_detected
verification_requested
render_brief_requested
contextual_reference_resolved
context_missing_for_reference
llm_router_used
llm_router_fallback_used
llm_conflict_resolved
event_creation_intent_detected
direct_catalog_search_detected
brief_workspace_selected
chat_search_selected
```

### `ActionPlan`

`ActionPlan` is the policy output. It decides which actions are allowed in this turn and resolves references using explicit request context.

```json
{
  "interface_mode": "brief_workspace",
  "workflow_stage": "supplier_searching",
  "tool_intents": ["update_brief", "search_items"],
  "search_requests": [],
  "verification_targets": [],
  "render_requested": false,
  "missing_fields": ["date_or_period"],
  "clarification_questions": ["На какую дату или период планируется мероприятие?"],
  "skipped_actions": []
}
```

Rules:

- `should_search_now` is a derived compatibility field: `search_items in action_plan.tool_intents`.
- `should_verify_now` is derived from `verify_supplier_status in action_plan.tool_intents`.
- `should_render_now` is derived from `render_event_brief in action_plan.tool_intents`.
- LLM output can suggest requested actions, but only `BriefWorkflowPolicy` can put tools into `ActionPlan.tool_intents`.
- `search_query` is deprecated in favor of `search_requests[]`. During migration, the HTTP response may include both `search_query` and `search_requests`, but backend orchestration must use `ActionPlan.search_requests`.

### `RouterDecision` v2 Compatibility Payload

The public `router` response can remain compact for API compatibility, but it must be assembled from `Interpretation + ActionPlan`:

```json
{
  "interface_mode": "brief_workspace",
  "intent": "mixed",
  "workflow_stage": "supplier_searching",
  "confidence": 0.84,
  "reason_codes": ["brief_update_detected", "search_action_detected"],
  "brief_update": {},
  "search_requests": [],
  "tool_intents": ["update_brief", "search_items"],
  "should_search_now": true,
  "missing_fields": ["date_or_period"],
  "clarification_questions": ["На какую дату или период планируется мероприятие?"],
  "user_visible_summary": null
}
```

### `VerificationTarget`

```json
{
  "item_id": "uuid",
  "supplier_inn": "7701234567",
  "supplier_name": "ООО Пример",
  "source": "visible_candidates"
}
```

Allowed target sources:

```text
selected_item_ids | candidate_item_ids | visible_candidates | explicit_item_id
```

No other source is allowed in the stateless first implementation.

### `SearchRequest`

```json
{
  "query": "световое оборудование корпоратив 120 человек Екатеринбург площадка без подвеса",
  "service_category": "свет",
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

`SearchRequest.filters` must be typed. Unknown filter keys from an LLM response or HTTP request are dropped during schema validation and never reach catalog search.

### `SupplierVerificationResult`

```json
{
  "supplier_name": "ООО Пример",
  "supplier_inn": "7700000000",
  "ogrn": null,
  "legal_name": null,
  "status": "not_verified",
  "source": "manual_not_verified",
  "checked_at": null,
  "risk_flags": ["verification_adapter_not_configured"],
  "message": "Поставщик не проверен автоматически"
}
```

Allowed `status` values:

```text
active | inactive | not_found | not_verified | error
```

The MVP adapter can return `not_verified` while the port and DTO are introduced. External adapters such as FNS EGRUL/EGRIP or DaData must be behind the same port and must not be called from domain code directly.

Verification semantics:

- `status=active` means the legal entity was found as active in the verification source.
- `status=active` does not mean the supplier is available on the event date.
- `status=active` does not mean ARGUS recommends the supplier.
- `status=active` does not mean an agency contract is currently valid.
- Assistant prose should say `юрлицо найдено как действующее в проверочном источнике`, not `подрядчик готов к мероприятию`.
- If several found items share one `supplier_inn`, `verify_supplier_status` is called once and the result is mapped back to all related item ids.

### `RenderedEventBrief`

```json
{
  "title": "Бриф мероприятия",
  "sections": [
    {
      "title": "Основная информация",
      "items": ["Тип: корпоратив", "Город: Екатеринбург"]
    }
  ],
  "open_questions": ["Дата мероприятия"],
  "evidence": {
    "selected_item_ids": [],
    "verification_result_ids": []
  }
}
```

The first renderer should be deterministic/template-based. LLM paraphrasing is optional later and must use only structured inputs.

## File Map

### Create

- `backend/app/features/assistant/domain/taxonomy.py` - event service categories, aliases, city aliases and action vocabulary.
- `backend/app/features/assistant/domain/slot_extraction.py` - deterministic extraction of event slots from a message.
- `backend/app/features/assistant/domain/action_detection.py` - deterministic detection of search, update, verification, render, selection and comparison actions.
- `backend/app/features/assistant/domain/event_brief_interpreter.py` - deterministic extraction plus LLM routing merge/fallback.
- `backend/app/features/assistant/domain/brief_workflow_policy.py` - workflow stage, missing-field policy and allowed next actions.
- `backend/app/features/assistant/domain/search_planning.py` - converts `search_requests[]` into executable catalog searches.
- `backend/app/features/assistant/domain/tool_executor.py` - bounded execution of approved backend tools.
- `backend/app/features/assistant/domain/response_composer.py` - safe Russian prose from router decision, brief state, search status, verification status and rendered brief.
- `backend/app/features/assistant/domain/brief_renderer.py` - deterministic final brief renderer.
- `backend/app/features/assistant/domain/llm_router/` - structured router
  prompt, schema allowlists, validation and deterministic-first merge. The
  current prompt builder is `prompt.py`.
- `backend/app/adapters/llm/assistant_router.py` - LM Studio/OpenAI-compatible adapter implementing the assistant LLM router port.
- `backend/app/adapters/supplier_verification/manual.py` - default adapter that returns `not_verified`.
- `backend/tests/fixtures/assistant_workflow_cases.json` - golden event-manager workflow dataset.
- `backend/tests/features/assistant/test_event_taxonomy.py`
- `backend/tests/features/assistant/test_slot_extraction.py`
- `backend/tests/features/assistant/test_action_detection.py`
- `backend/tests/features/assistant/test_event_brief_interpreter.py`
- `backend/tests/features/assistant/test_brief_workflow_policy.py`
- `backend/tests/features/assistant/test_search_planning.py`
- `backend/tests/features/assistant/test_tool_executor.py`
- `backend/tests/features/assistant/test_response_composer.py`
- `backend/tests/features/assistant/test_brief_renderer.py`
- `backend/tests/features/assistant/test_workflow_golden_cases.py`
- `backend/tests/features/assistant/test_supplier_verification.py`

### Modify

- `backend/app/features/assistant/dto.py` - add v2 brief fields, normalized `ServiceNeed`, assistant interface mode, workflow state, typed filters, `Interpretation`, `ActionPlan`, `ToolResults`, `SearchRequest`, `VerificationTarget`, `ToolIntent`, `SupplierVerificationResult`, `RenderedEventBrief`, `ChatTurn`, `VisibleCandidate`, `candidate_item_ids` request context and `RouterDecision` compatibility fields.
- `backend/app/features/assistant/brief.py` - merge new fields, dedupe list values, preserve explicit scalar overwrite rules.
- `backend/app/features/assistant/ports.py` - update `AssistantRouter.route()` context and add ports for structured LLM routing, item details, supplier verification and brief rendering.
- `backend/app/features/assistant/router.py` - keep a compatibility facade or replace it with `EventBriefInterpreter` behind the same assistant router port.
- `backend/app/features/assistant/use_cases/chat_turn.py` - orchestrate interpreter, policy, tool executor and response composer.
- `backend/app/entrypoints/http/schemas/assistant.py` - expose v2 brief, `recent_turns`, `visible_candidates`, `candidate_item_ids`, `action_plan`, `search_requests[]`, verification results and rendered brief.
- `backend/app/entrypoints/http/dependencies.py` - wire LLM router adapter, manual supplier verification adapter and assistant tool dependencies.
- `docs/api/openapi.yaml` - update assistant contract after backend schemas are stable.
- `docs/agent/search.md` - document the event-brief orchestrator, evidence rules and new response layers.
- `docs/agent/entity-resolution.md` - note that supplier verification is explicit and separate from CSV-to-contractor resolution.

### Review Existing

- `backend/app/features/catalog/use_cases/search_price_items.py`
- `backend/app/adapters/sqlalchemy/price_items.py`
- `backend/tests/features/catalog/use_cases/test_search_price_items.py`
- `backend/tests/features/catalog/use_cases/test_import_prices_csv.py`
- `test_files/prices.csv`

These already cover part of keyword fallback. Strengthen them; do not duplicate catalog search logic in assistant.

## Phase 0: Event Workflow Evaluation Dataset

**Outcome:** Router/interpreter behavior is measurable before LLM behavior affects users.

- [ ] Create `backend/tests/fixtures/assistant_workflow_cases.json` with 25-40 seed cases.
- [ ] Include `message`, `brief_before`, `recent_turns`, `visible_candidates`, `candidate_item_ids`, expected `interface_mode`, expected intent, expected workflow stage, expected brief patch, expected `ActionPlan.tool_intents`, expected search categories, expected verification targets, expected missing fields and expected verification/render behavior.
- [ ] Mark `brief_workspace` cases separately from `chat_search` cases so the frontend behavior is testable.
- [ ] Add `backend/tests/features/assistant/test_workflow_golden_cases.py` that runs with deterministic or fake LLM behavior only.
- [ ] Keep real LM Studio evaluation as an integration test that is skipped unless explicitly enabled.

Seed phrases:

```text
Нужно организовать корпоратив на 120 человек в Екатеринбурге
найди подрядчика по свету в Екатеринбурге
покажи радиомикрофоны у поставщиков с НДС
а что есть по свету на 300 гостей?
надо закрыть welcome-зону
в Екате кто сможет быстро?
добавь, что площадка без подвеса, и посмотри фермы
Бюджет около 2 млн, город Екатеринбург
На 120 человек в Екатеринбурге нужен кейтеринг до 2500 на гостя
Ок, тогда найди сцену и свет под это
Площадка уже есть, монтаж только ночью
Нужен звук, но без премиума, что-то рабочее
проверь найденных подрядчиков
проверь найденных подрядчиков, но без visible_candidates/candidate_item_ids
сформируй итоговый бриф
Добавь в подборку второй вариант
Сравни первые два по цене
```

Focused check:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_workflow_golden_cases.py -v
```

## Phase 1: Event Brief Core

**Outcome:** Assistant can collect a real event brief and ask useful next questions without searching prematurely.

- [ ] Extend `BriefState` to v2 fields.
- [ ] Add `AssistantInterfaceMode` with `brief_workspace` and `chat_search`.
- [ ] Add `EventBriefWorkflowState`.
- [ ] Add deterministic detection for explicit event creation/planning phrases that should open the brief workspace.
- [ ] Add deterministic detection for direct contractor/catalog search phrases that should keep the UI chat-only.
- [ ] Add deterministic slot extraction for event type, concept, event goal, format, city, date, audience size, venue status, venue constraints, budget total, budget per guest, catering format, technical requirements and service needs.
- [ ] Add missing-field policy for event intake: date/period, city, audience size, venue status, budget, concept/level and required service blocks.
- [ ] Make `ResponseComposer` ask 1-3 highest-value questions per turn; the rest should be represented as `brief.open_questions`.

Acceptance:

```text
Input:
Нужно организовать корпоратив на 120 человек в Екатеринбурге

Expected:
brief.event_type = корпоратив
brief.city = Екатеринбург
brief.audience_size = 120
workflow_stage = clarifying
interface_mode = brief_workspace
should_search_now = false unless user also asks to search
clarification_questions include date/period, venue status, budget or concept
```

Direct search acceptance:

```text
Input:
найди подрядчика по свету в Екатеринбурге

Expected:
interface_mode = chat_search
brief panel is not required by API/UI state
search request category = свет
clarification_questions ask only search-relevant missing fields when needed
found_items are rendered inline in chat after search
```

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_slot_extraction.py -v
uv run --project backend pytest backend/tests/features/assistant/test_brief_workflow_policy.py -v
uv run --project backend pytest backend/tests/features/assistant/test_response_composer.py -v
```

## Phase 2: Service Planning And Domain Taxonomy

**Outcome:** Brief facts are translated into event-service needs, not just text keywords.

- [ ] Add service taxonomy for `звук`, `свет`, `сценические конструкции`, `мультимедиа`, `кейтеринг`, `welcome-зона`, `персонал`, `логистика`, `декор`, `мебель`, `площадка`.
- [ ] Add aliases such as `радики -> радиомикрофоны`, `Екат -> Екатеринбург`, `фермы -> сценические конструкции`, `экран -> мультимедиа`.
- [ ] Add service bundles by event type and phrase: `welcome-зона` expands to registration desk, hostesses/personnel, navigation, brand wall/photo zone and optional welcome drink.
- [ ] Add venue-constraint implications: `без подвеса` suggests ground support, light stands, scenic structures and floor-based multimedia.
- [ ] Separate `required_services`, `must_have_services` and `nice_to_have_services`.

Acceptance:

```text
Input:
Площадка без подвеса, нужен корпоратив на 300 человек

Expected:
brief.venue_constraints includes площадка без подвеса
suggested search categories include сценические конструкции, свет, мультимедиа
assistant does not claim suppliers or prices until search_items returns rows
```

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_event_taxonomy.py -v
uv run --project backend pytest backend/tests/features/assistant/test_action_detection.py -v
```

## Phase 3: Structured LLM Interpreter

**Outcome:** LLM helps interpret messy event-manager language now, while code validates and bounds the result.

Architecture:

```text
RuleBasedEventSignals
  -> LLMStructuredRouterPort
      -> adapters/llm/assistant_router.py performs LM Studio/OpenAI-compatible call
      -> strict JSON
  -> EventBriefInterpreter validates, merges and falls back
```

- [ ] Keep the stable assistant router port:

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

- [ ] Add `LLMStructuredRouterPort` to assistant ports.
- [ ] Implement network calls only in `backend/app/adapters/llm/assistant_router.py`.
- [ ] Build prompts with message, active brief, recent turns, visible candidates, deterministic signals, allowed interface modes, allowed intents, allowed tool intents and strict JSON schema.
- [ ] Include `interface_mode` in the LLM schema and validate it against deterministic event-creation and direct-search signals.
- [ ] Validate JSON into DTOs; clamp confidence to `0.0..1.0`; drop unknown fields and unknown enum values.
- [ ] Merge deterministic first, LLM second. Deterministic facts always win for brief fields, selected ids, typed filters and explicit UI mode signals.
- [ ] If LLM tries to open a brief workspace for a direct contractor search, keep `chat_search` and add `llm_conflict_resolved`.
- [ ] Allow LLM to enrich `search_requests`, `missing_fields`, `clarification_questions` and `user_visible_summary` only when it does not conflict.
- [ ] If LLM conflicts with deterministic extraction, keep deterministic data and add `llm_conflict_resolved`.
- [ ] If LLM JSON is invalid, unsafe or confidence is below `0.55`, use deterministic fallback and add `llm_router_fallback_used`.
- [ ] Unit tests must use a fake LLM adapter with fixed outputs.

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_event_brief_interpreter.py -v
uv run --project backend pytest backend/tests/features/assistant/test_workflow_golden_cases.py -v
```

## Phase 4: Backend Tools And Bounded Tool Execution

**Outcome:** Chat orchestration uses explicit backend tools and cannot drift into arbitrary agent behavior.

Minimum tools:

- [ ] `update_brief`: merge `BriefPatch` into `BriefState` with list dedupe and scalar overwrite rules.
- [ ] `search_items`: execute one planned catalog search through the existing catalog use case.
- [ ] `get_item_details`: load one catalog item detail through an existing or new catalog detail use case.
- [ ] `verify_supplier_status`: verify suppliers by INN/OGRN/name through `SupplierVerificationPort`.
- [ ] `render_event_brief`: build deterministic structured final brief.

Next tools after the core scenario is stable:

- [ ] `select_item`: add explicit user-selected item ids to `BriefState.selected_item_ids`.
- [ ] `compare_items`: compare selected/found item rows by hydrated fields only.
- [ ] `estimate_budget_from_selected_items`: compute rough budget only from selected rows, explicit quantities and real catalog prices.

Execution rules:

- `ToolExecutor` accepts validated `ActionPlan.tool_intents` from policy, not raw LLM commands.
- Initial cap: at most 3 tool calls per turn.
- `verify_supplier_status` may run only for `selected_item_ids`, `candidate_item_ids`, `visible_candidates` or explicit item ids from the message.
- `verify_supplier_status` must not use stale implicit server memory to decide what `найденных подрядчиков` means.
- Items without INN are marked `not_verified` with risk flag `supplier_inn_missing`.
- Verification calls are deduped by `supplier_inn`; one legal entity check can map to multiple item ids.
- If the verification adapter is not configured, the default manual adapter returns `not_verified` instead of failing the turn.
- Tool results are structured DTOs and are included separately from `message`.

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_tool_executor.py -v
uv run --project backend pytest backend/tests/features/assistant/test_supplier_verification.py -v
```

## Phase 5: Search Planner And Multi-Search

**Outcome:** Assistant searches by service groups instead of sending one raw query to the catalog.

- [ ] Add `SearchPlanner` that accepts `RouterDecision`, brief before/after and workflow stage.
- [ ] Execute up to 3 planned searches per chat turn.
- [ ] Use typed filters from brief and request: `supplier_city_normalized`, `category`, `supplier_status_normalized`, `has_vat`, `vat_mode`, `unit_price_min`, `unit_price_max`.
- [ ] Generate query text with event type, audience size, city, venue constraints, budget preference and concept when useful.
- [ ] Preserve flat `found_items` for compatibility and add grouping markers when API schemas are updated: `result_group`, `matched_service_category`, `matched_service_categories[]`.
- [ ] Deduplicate found items by `id` across searches; keep the first priority group and append all matched categories.
- [ ] Keep catalog search logic inside catalog use cases.

Acceptance:

```text
Input:
подбери кейтеринг и свет на 120 человек в Екатеринбурге

Expected:
2 search_requests
search group 1 = кейтеринг
search group 2 = свет
found_items are grouped or tagged by service category
```

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_search_planning.py -v
uv run --project backend pytest backend/tests/features/assistant/use_cases/test_chat_turn.py -v
```

## Phase 6: Supplier Verification

**Outcome:** The assistant can check supplier status through a controlled port without coupling CSV import to contractor resolution.

- [ ] Add `SupplierVerificationPort`:

```python
class SupplierVerificationPort(Protocol):
    async def verify_by_inn_or_ogrn(
        self,
        *,
        inn: str | None,
        ogrn: str | None,
        supplier_name: str | None,
    ) -> SupplierVerificationResult: ...
```

- [ ] Add `ManualNotVerifiedSupplierVerificationAdapter` for MVP and unit tests.
- [ ] Add fake adapter for tests with deterministic active/inactive/not_found cases.
- [ ] Keep external adapters optional and outside this plan unless explicitly approved.
- [ ] Do not call contractor entity resolution from supplier verification by default.
- [ ] Preserve original catalog facts from `price_items` even when verification returns a normalized legal name.

Acceptance:

```text
Input:
проверь найденных подрядчиков

Expected:
items are resolved only from selected_item_ids, candidate_item_ids, visible_candidates or explicit item ids
items with supplier_inn receive verification_results
items without supplier_inn receive not_verified + supplier_inn_missing
same supplier_inn is verified once and mapped to all related item ids
assistant message does not claim legal active status unless verification result says active
assistant message does not claim date availability, recommendation or active contract even when status=active

Input:
проверь найденных подрядчиков

Without:
selected_item_ids, candidate_item_ids, visible_candidates or explicit item ids

Expected:
clarification, no verification_results, no supplier status invented
```

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_supplier_verification.py -v
uv run --project backend pytest backend/tests/features/assistant/use_cases/test_chat_turn.py -v
```

## Phase 7: Render Event Brief

**Outcome:** The assistant can return a finished working brief as a structured artifact.

- [ ] Add `BriefRenderer` with deterministic templates.
- [ ] Render sections: basic event info, concept and level, venue and constraints, service blocks, selected candidates, supplier verification, budget notes and open questions.
- [ ] Include only selected or explicitly provided catalog rows in candidate sections.
- [ ] If `selected_item_ids` is empty, render found catalog rows only as `кандидаты найдены, но не выбраны`; do not turn `found_items` into selected proposal lines.
- [ ] Budget notes must not sum or treat `found_items` as an estimate unless the items are selected and quantities/prices are explicit.
- [ ] Include verification statuses only from `verification_results`.
- [ ] Put unknowns in `open_questions` instead of inventing details.

Acceptance:

```text
Input:
сформируй итоговый бриф

Expected:
rendered_brief exists
message says the brief is prepared
rendered brief sections include open questions
catalog facts appear only if backed by selected_items/found_items/detail/verification_results
```

Focused checks:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_brief_renderer.py -v
uv run --project backend pytest backend/tests/features/assistant/test_response_composer.py -v
```

## Phase 8: Catalog Search Regression Dependency From `prices.csv`

**Outcome:** Short professional queries keep working when embeddings are weak.

This is a catalog quality dependency for the assistant, not assistant orchestration logic. The current catalog search already has keyword fallback over imported Postgres rows. This phase strengthens catalog regression data from `test_files/prices.csv` while keeping the assistant dependent on the catalog search port only.

- [ ] Import `test_files/prices.csv` in an integration-style fixture or reuse existing CSV import tests to create representative `price_items`.
- [ ] Build regression cases from actual CSV columns: `id`, `name`, `source_text`, `section`, `category`, `supplier`, `supplier_inn`, `supplier_city`, `has_vat`, `supplier_status`.
- [ ] Keep runtime keyword fallback over imported `price_items`; do not query raw CSV files at runtime.
- [ ] Keep all keyword fallback implementation inside catalog use cases/adapters; do not duplicate keyword matching in assistant services.
- [ ] Cover exact supplier names, INNs, city aliases, professional abbreviations, VAT phrases, status phrases, category/section words and short service terms.
- [ ] Keep first implementation simple: normalized exact match plus case-insensitive containment over `name`, `source_text`, `supplier`, `supplier_inn` and `external_id`.
- [ ] Include simple fallback/filter parsing for `has_vat`, `category`, `section`, `supplier_city` and `supplier_status`.
- [ ] Keep sparse vectors, RRF, trigram tuning and full-text ranking as later improvements after evaluation data shows the need.

Required regression examples:

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
uv run --project backend pytest backend/tests/features/catalog/use_cases/test_import_prices_csv.py -v
```

## Phase 9: API And Frontend Compatibility

**Outcome:** The UI can support the target workflow while preserving evidence separation.

- [ ] Update `docs/api/openapi.yaml` after backend schemas are implemented.
- [ ] Add top-level response `ui_mode` or equivalent `router.interface_mode` so the frontend can choose between brief workspace and chat-only search.
- [ ] Keep response layers: `message`, `router`, `brief`, `found_items`.
- [ ] Add response layers: `verification_results`, `rendered_brief`, and optional grouped item metadata.
- [ ] Add `router.workflow_stage`, `router.search_requests[]`, `router.tool_intents[]`, `router.reason_codes[]`, `router.clarification_questions[]`.
- [ ] Add optional response `action_plan` after backend DTOs stabilize, or include equivalent fields in `router` during the compatibility phase.
- [ ] Add optional request `recent_turns[]`.
- [ ] Add optional request `visible_candidates[]` with `ordinal` and `item_id` for selection/comparison turns.
- [ ] Add optional request `candidate_item_ids[]` for verification turns such as `проверь найденных подрядчиков`.
- [ ] Add v2 brief fields to frontend DTOs after backend response is stable.
- [ ] In `brief_workspace`, render chat + draft brief + grouped candidates + verification + rendered brief.
- [ ] In `chat_search`, render a simple chat timeline with clarifying questions and inline catalog result cards; do not open the draft brief panel unless the user asks to start an event or brief.
- [ ] Preserve legacy request `brief.budget` during rollout.
- [ ] Keep `found_items` cards/table visually separate from assistant prose.

## Rollout Order

1. MVS-1: land the event workflow golden dataset with deterministic/fake LLM tests.
2. MVS-1: land `BriefState` v2 compatibility fields, workflow state and missing-field policy.
3. MVS-1: add `Interpretation -> ActionPlan -> ToolResults -> ChatTurnResponse` DTOs and deterministic response composition.
4. MVS-1: add manual-not-verified supplier verification adapter and deterministic brief renderer skeleton without expanding external integrations.
5. MVS-2: add taxonomy, service bundles, venue-constraint implications and normalized `service_needs`.
6. MVS-2: add multi-search planner, grouped result metadata, `visible_candidates` and `candidate_item_ids`.
7. MVS-3: add structured LLM interpreter with deterministic-first merge and fallback.
8. MVS-3: add supplier verification target resolution, INN dedupe and complete render_event_brief behavior.
9. Catalog dependency: strengthen keyword fallback regression coverage from imported `prices.csv` in catalog tests/use cases.
10. Update OpenAPI, docs and frontend DTOs after backend tests pass.
11. Remove old single-query orchestration paths only after the UI no longer depends on `search_query`.

## Acceptance Criteria

- ARGUS assistant is implemented as an event-brief copilot with catalog-backed supplier search, not as a general free-running agent.
- One chat turn is bounded by approved tool intents and a small tool-call cap.
- Interpreter receives `message`, active `BriefState`, optional `recent_turns`, optional `visible_candidates` and optional `candidate_item_ids`.
- Router/interpreter returns an interface mode so explicit event creation opens the brief workspace and direct contractor search stays chat-only.
- LLM is used now for structured interpretation, but all output is validated and merged with deterministic facts.
- `Interpretation`, `ActionPlan`, `ToolResults` and `ChatTurnResponse` are separate DTO layers.
- `should_search_now` is derived from `ActionPlan.tool_intents`, not independently decided by the LLM.
- `BriefState` supports concept, event goal, format, budget semantics, venue constraints, normalized service needs, service priorities and selected item ids.
- `SearchPlanner` can run multiple grouped catalog searches without duplicating catalog search logic.
- `verify_supplier_status` exists as a backend tool through `SupplierVerificationPort`.
- Verification targets come only from selected item ids, candidate item ids, visible candidates or explicit item ids.
- Supplier verification is deduped by INN and does not imply date availability, recommendation or active contract.
- `render_event_brief` exists as a backend tool and produces a structured brief from state and evidence.
- Final brief does not treat found candidates as selected candidates unless `selected_item_ids` exist.
- `ResponseComposer` asks 1-3 useful questions and does not put item-specific catalog facts in prose.
- Keyword fallback has regression coverage from imported `test_files/prices.csv` as a catalog-search dependency, not assistant logic.
- Golden workflow dataset can run in unit/CI mode without Postgres, Redis, Qdrant, LibreOffice, Tesseract or LM Studio unless a test is explicitly marked integration.

## Verification Commands

Run focused tests first:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_event_taxonomy.py -v
uv run --project backend pytest backend/tests/features/assistant/test_slot_extraction.py -v
uv run --project backend pytest backend/tests/features/assistant/test_action_detection.py -v
uv run --project backend pytest backend/tests/features/assistant/test_event_brief_interpreter.py -v
uv run --project backend pytest backend/tests/features/assistant/test_brief_workflow_policy.py -v
uv run --project backend pytest backend/tests/features/assistant/test_search_planning.py -v
uv run --project backend pytest backend/tests/features/assistant/test_tool_executor.py -v
uv run --project backend pytest backend/tests/features/assistant/test_supplier_verification.py -v
uv run --project backend pytest backend/tests/features/assistant/test_brief_renderer.py -v
uv run --project backend pytest backend/tests/features/assistant/test_response_composer.py -v
uv run --project backend pytest backend/tests/features/assistant/test_workflow_golden_cases.py -v
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
