# Event Brief Assistant

ARGUS assistant is an event-brief copilot with catalog-backed supplier search.
It is not a general autonomous agent and not a prose wrapper around catalog
search.

Primary product flows:

```text
event request
  -> brief collection
  -> service planning
  -> catalog candidate search
  -> supplier verification
  -> final event brief

direct contractor/service search
  -> search clarification
  -> catalog candidates directly in chat
```

Detailed rollout plans:

- `docs/plans/catalog-first-refactor/07-event-brief-assistant-orchestrator.md`
- `docs/plans/catalog-first-refactor/08-event-brief-e2e-scenario.md`

Current implementation pointers:

- Public HTTP contract: `docs/api/openapi.yaml`.
- Backend DTO contract: `backend/app/features/assistant/dto.py`.
- LangGraph runtime: `backend/app/features/assistant/agent_graph.py`.
- LangChain planner adapter:
  `backend/app/adapters/llm/assistant_agent_planner.py`.
- Plan 07 phase prompt handoff:
  `docs/plans/prompts/07-event-brief-assistant-orchestrator-prompts.md`.
- Frontend UI state adapter: `frontend/src/utils/assistantUiState.ts`.
- Frontend request context builder: `frontend/src/utils/assistantRequest.ts`.

## UX Modes

The backend returns an explicit `ui_mode`; the frontend must not guess from
message text alone.

### `brief_workspace`

Use when the user explicitly creates, prepares, plans, organizes or renders an
event:

```text
Нужно организовать корпоратив на 120 человек в Екатеринбурге
Собери бриф на конференцию для партнеров
Готовим презентацию продукта, нужна площадка, свет и кейтеринг
```

Expected UI:

```text
chat timeline + draft brief panel + service groups + catalog candidates
  + supplier verification + final rendered brief
```

The assistant updates `BriefState`, asks high-value brief questions, plans
service blocks, searches candidates when requested or policy-allowed, verifies
suppliers when explicitly asked, and renders a final structured brief.

### `chat_search`

Use when the user only wants a contractor, supplier, item, price or service:

```text
Найди подрядчика по свету в Екатеринбурге
Есть кейтеринг до 2500 на гостя?
Покажи радиомикрофоны у поставщиков с НДС
```

Expected UI:

```text
single chat timeline with clarifying questions and inline catalog cards
```

Do not open the draft brief panel in this mode. Ask only search-specific
questions such as city, service category, VAT mode, price band or task format.
Switch to `brief_workspace` only when the user explicitly asks to create, save
or render an event brief.

If the mode is ambiguous, default to `chat_search` and ask whether the user
wants to start an event brief.

## One-Turn Orchestrator

One user message runs one bounded LangGraph chat turn:

```text
POST /assistant/chat
  -> AssistantGraphRunner
      -> prepare_input
      -> agent_plan
      -> validate_tool_calls
      -> execute_tools
      -> compose_final_response
      -> ChatTurnResponse
```

The assistant uses a LangGraph loop, but tool execution is backend-gated.
The LLM planner may propose tool calls; backend validation still controls tool
names, arguments, request context and call budget. Initial defaults should be:

```text
max_tool_calls_per_turn = 3
max_llm_retries = 1
```

LLM assistance is allowed only through structured LangChain/LangGraph planner
output behind validated DTOs. The LLM must not:

- execute tools directly without backend validation;
- generate SQL or arbitrary HTTP requests;
- write final user prose for catalog facts;
- invent prices, suppliers, contacts, INNs, cities, statuses or availability;
- decide tool execution without backend policy validation.

## Graph State Flow

Do not put facts, policy and tool authorization into one legacy router object.
The LangGraph runtime keeps planner output, backend validation, tool results
and response projection as separate graph state updates.

```text
LangChainAssistantAgentPlanner
  -> AssistantAgentPlan
     message, interface_mode, workflow_stage, brief_update,
     proposed tool_calls and clarification questions

AssistantGraphRunner.validate_tool_calls
  -> ActionPlan
     backend-approved tool_intents, search_requests and skipped tool reasons

AssistantGraphRunner.execute_tools
  -> graph state
     found_items, merged brief and skipped tool reasons

AssistantGraphRunner.compose_response
  -> AssistantChatResponse
     safe message, ui_mode, router/action diagnostics, brief and evidence
```

`RouterDecision` can remain as a public compatibility/debug payload, but it is
assembled from graph state. It is not the object that authorizes tool
execution.

Derived compatibility fields:

```text
should_search_now = "search_items" in action_plan.tool_intents
should_verify_now = "verify_supplier_status" in action_plan.tool_intents
should_render_now = "render_event_brief" in action_plan.tool_intents
```

`search_query` is deprecated in favor of `search_requests[]`. During migration,
the HTTP response may include both, but orchestration must use
`ActionPlan.search_requests`.

## Brief State

`BriefState` is structured state, not a prose summary. Target v2 fields:

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

Field semantics:

- `service_needs`: normalized model used by policy and search planning.
- `required_services`: compatibility/UI projection of explicitly requested
  service blocks.
- `must_have_services`: explicitly mandatory blocks only.
- `nice_to_have_services`: policy suggestions; never selected or mandatory.
- `technical_requirements`: execution requirements, not service categories.
- `venue_constraints`: venue-caused constraints such as `площадка без подвеса`.
- `constraints`: non-venue business constraints.
- `preferences`: soft guidance such as `без премиума` or `быстро`.
- `selected_item_ids`: explicit user choices; found candidates do not enter
  this list automatically.

Budget fields must not be collapsed:

- `budget_total`: total event budget.
- `budget_per_guest`: per-person budget such as `до 2500 на гостя`.
- `budget_notes`: unclear budget prose.

## Workflow Stages

Event-brief workspace stages:

```text
intake
clarifying
service_planning
supplier_searching
supplier_verification
brief_ready
brief_rendered
```

Chat-only search can use transient stages:

```text
search_clarifying
searching
search_results_shown
supplier_verification
```

Transition matrix for the event workspace:

| Current stage | User signal | Required facts | Next stage | Allowed tools |
| --- | --- | --- | --- | --- |
| `intake` | describes event | event type, city or audience can be partial | `clarifying` | `update_brief` |
| `clarifying` | gives date, budget, venue or concept | enough facts for planning, not necessarily complete | `service_planning` | `update_brief` |
| `service_planning` | says `подбери`, `найди`, `посмотри` | service category or inferred service need | `supplier_searching` | `search_items` |
| `supplier_searching` | says `добавь второй` | `visible_candidates` has ordinal and item id | `supplier_searching` | `select_item` |
| `supplier_searching` | says `проверь найденных подрядчиков` | selected ids, candidate ids, visible candidates or explicit item ids | `supplier_verification` | `verify_supplier_status` |
| `supplier_verification` | says `сформируй бриф` | non-empty brief exists | `brief_rendered` | `render_event_brief` |

Important rule:

```text
service inference != catalog search
```

For example, `площадка без подвеса` can add policy suggestions for ground
support and floor lighting, but must not show catalog cards until search
actually runs.

## Request Context

The first implementation is stateless on the backend side except for
`BriefState` and explicit UI context passed by the client. The backend must not
resolve `найденных`, `второй вариант`, `первые два` or `эти подрядчики` from
hidden server memory.

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

- Selection and comparison resolve ordinal references only through
  `visible_candidates`.
- `Проверь найденных подрядчиков` can target only
  `BriefState.selected_item_ids`, request `candidate_item_ids`, request
  `visible_candidates`, or explicit item ids in the message.
- If no candidate context exists, return a clarification and no
  `verification_results`.
- `visible_candidates` and `candidate_item_ids` are request-only context. The
  response does not echo them; clients must rebuild them from the candidate cards
  they keep visible.
- `selected_item_ids` lives inside `BriefState`, not as top-level request
  context.
- Persisted chat history can be added later, but current behavior must not
  silently depend on it.

## Backend Tools

Backend tools are explicit Python services/use cases, not free-form agent
skills:

```text
update_brief
search_items
get_item_details
select_item
compare_items
verify_supplier_status
render_event_brief
```

`AssistantGraphRunner` executes only tool calls approved by backend validation.
LLM output can suggest actions but cannot authorize them.

Tool execution rules:

- Cap search at the configured per-turn limit, initially 3 service searches.
- Search through catalog ports/services; assistant feature code must not import
  catalog internals or run direct SQL.
- Verification dedupes by `supplier_inn` before calling the verification port.
- Missing INN produces `not_verified` with a risk flag such as
  `supplier_inn_missing`.
- If the external verification adapter is unavailable, return
  `not_verified` from the manual adapter instead of claiming status.

## Evidence Rules

`price_items` in Postgres is the source of truth for catalog facts. Assistant
prose is not.

Facts that must be backed by `found_items`, opened item details or
`verification_results`:

```text
price
unit
supplier
supplier city
phone
email
INN
OGRN
status
source text
date availability
```

`found_items` are candidates, not selected proposal lines. Final briefs must not
turn all found rows into selected candidates. Use only `selected_item_ids` for
chosen candidates.

Registry `active` status means the legal entity was found as active in the
verification source. It does not mean:

- supplier availability on the event date;
- ARGUS recommendation;
- active agency contract;
- confirmed booking.

Safe phrasing:

```text
Нашел кандидатов в каталоге.
Позиции ниже - предварительная подборка.
Юрлицо найдено как действующее в проверочном источнике.
По позициям без ИНН нужна ручная проверка.
```

Unsafe phrasing:

```text
Этот поставщик точно доступен на дату.
Это лучший вариант.
Цена будет такой-то, если строки каталога нет.
Подрядчик работает, хотя verification_results нет.
```

## Response Composer

The response composer builds user-facing Russian text from structured state and
tool results. It should:

1. Confirm the current work state in one sentence.
2. Mention brief updates when they happened.
3. Mention searches, verification or rendering when they ran.
4. Point to evidence-backed UI sections instead of restating catalog facts.
5. Ask 1-3 next questions.

Mode-specific behavior:

- In `brief_workspace`, mention what changed in the brief and point the user to
  the draft brief panel.
- In `chat_search`, keep the answer compact, ask only search clarifications and
  place catalog cards directly below the assistant message.
- Do not say `обновил бриф` or show the draft brief UI in `chat_search` unless
  the user explicitly asks to create or save an event brief.

## Evaluation

Before enabling real LLM behavior, add or update golden cases for:

- pure brief intake;
- direct chat-only catalog search;
- mixed brief update plus search;
- contextual phrases such as `под это`, `тогда`, `в Екате`;
- venue constraints and budget per guest;
- service bundles such as welcome zone;
- selection and comparison with and without `visible_candidates`;
- supplier verification with and without candidate context;
- final brief rendering with and without selected item ids.

Core behavior must pass with deterministic extraction and fake LLM responses.
Real LM Studio checks should be optional integration tests.
