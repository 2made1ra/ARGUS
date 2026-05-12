# Event Brief E2E Scenario And UX Architecture

**Goal:** Define the product workflow for ARGUS as an event-manager copilot that goes from incoming request to working brief, catalog-backed candidates, supplier verification and final structured brief.

**Relationship to implementation plan:** `docs/plans/catalog-first-refactor/07-event-brief-assistant-orchestrator.md` describes the backend implementation. This document describes the target UX, workflow states and acceptance behavior.

---

## Product Direction

ARGUS assistant is not a general agent and not a chat wrapper around search.

```text
ARGUS assistant is an event-brief copilot with catalog-backed supplier search.
```

The user is not primarily "searching". The user is preparing an event. The assistant should guide the manager through:

```text
request intake
  -> brief collection
  -> service planning
  -> catalog candidate search
  -> supplier verification
  -> final event brief
```

This is the primary flow only when the user explicitly creates, prepares, plans or organizes an event. ARGUS also supports a second main flow:

```text
direct contractor/service search
  -> search clarification
  -> catalog candidates directly in chat
```

The product must not force the event-brief workspace on users who only want to find a contractor, supplier, item or price row.

The catalog remains evidence-backed. Prices, suppliers, cities, contacts, INNs, statuses and source text are shown through cards/tables and verification results, not invented in assistant prose.

## Two Main UX Flows

### Flow A: Event Brief Workspace

Trigger examples:

```text
Нужно организовать корпоратив на 120 человек в Екатеринбурге.
Собери бриф на конференцию для партнёров.
Готовим презентацию продукта, нужна площадка, свет и кейтеринг.
```

Expected UI:

```text
Chat + draft brief panel + service groups + catalog candidates + verification + final brief
```

The user is preparing an event. The assistant keeps and updates `BriefState`, shows the draft brief, asks high-value brief questions, plans service blocks, searches candidates, verifies suppliers and can render the final brief.

### Flow B: Chat-Only Catalog Search

Trigger examples:

```text
Найди подрядчика по свету в Екатеринбурге.
Есть кейтеринг до 2500 на гостя?
Покажи радиомикрофоны у поставщиков с НДС.
```

Expected UI:

```text
Simple chat timeline with clarifying questions and inline catalog result cards
```

The user is searching, not creating an event. The assistant may ask search-specific questions such as city, category, budget, VAT mode or date if needed, then returns catalog positions directly inside the chat. The draft brief panel stays hidden unless the user explicitly asks to start an event or save the search into a brief.

## State And Context Assumptions

The first implementation is stateless on the backend side except for `BriefState` passed by the client. The frontend must pass explicit context when the user refers to visible results.

Request context should include:

```json
{
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

UX rules:

- `добавь второй вариант` works only if the UI sends `visible_candidates` with ordinal mapping.
- `сравни первые два` works only if the UI sends `visible_candidates` with both ordinals.
- `проверь найденных подрядчиков` works only if the UI sends `candidate_item_ids`, `visible_candidates`, or the brief contains `selected_item_ids`.
- Without this context, the assistant asks a clarification and does not invent verification results.
- The UI must not rely on backend-hidden chat memory for visible candidate references in the first implementation.

## UX Principles

- The chat is always the primary interaction surface.
- In event-creation flow, the brief is the primary state.
- In direct-search flow, the search context is lightweight and lives inside the chat turn/context, not in a full event brief UI.
- The assistant asks 1-3 high-value questions per turn; in event-brief mode the full missing-field list belongs in the brief panel, while in chat-search mode only search-relevant missing fields are asked.
- Search results are candidates, not selected proposal lines.
- Found candidates are not selected candidates until the user explicitly selects them.
- Supplier verification is explicit and visible; unverified suppliers are not silently treated as safe.
- Registry `active` status is not event-date availability, recommendation or proof of an active agency contract.
- The final brief is a structured artifact, not just a chat answer.
- The assistant can sound natural, but must keep evidence and prose separate.

## Main Screen Structure

Recommended event-brief workspace UI:

```text
Left: chat timeline
Right: draft brief panel
Below or secondary panel: catalog candidates grouped by service
Optional drawer: selected items and supplier verification
Final mode: rendered event brief
```

Recommended chat-only search UI:

```text
Single chat timeline
Assistant clarification questions
Inline catalog candidate cards grouped by requested service when useful
Inline supplier verification status when the user asks to verify
No draft brief panel unless event creation intent is detected
```

### Chat Timeline

The chat shows:

- user messages;
- assistant summary and next questions;
- status lines such as "обновил бриф", "запустил подбор", "проверка подрядчиков не настроена";
- no unchecked supplier/price claims in prose.

### Draft Brief Panel

The draft brief panel shows:

- event type;
- event goal;
- concept;
- format;
- city;
- date/period;
- audience size;
- venue status;
- venue constraints;
- budget total;
- budget per guest;
- event level;
- service blocks;
- selected items;
- open questions.

Fields with unknown values should be visible as open questions instead of hidden.

### Candidate Results

Catalog candidate groups show:

- service category group;
- item cards from `found_items`;
- supplier, city, unit, unit price and source snippet only from hydrated Postgres rows;
- backend `match_reason`;
- selection controls that create `selected_item_ids`.

The UI must keep candidate cards separate from the assistant message.

### Supplier Verification

Verification results show:

- supplier name and INN from catalog row;
- verification status;
- source adapter;
- checked timestamp when available;
- risk flags;
- manual verification note when automatic adapter is not configured.

Unverified is a valid state, not an error.

### Rendered Brief

Rendered brief shows:

- basic event information;
- concept and level;
- venue and constraints;
- service blocks;
- selected candidate summary;
- supplier verification summary;
- budget notes;
- open questions.

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

Chat-only search can use a narrower transient state:

```text
search_clarifying
searching
search_results_shown
supplier_verification
```

The backend can still return the same `router`, `found_items` and `verification_results` shapes, but the UI chooses layout from `interface_mode`.

### Stage Transition Matrix

| Current stage | User signal | Required facts | Next stage | Allowed tools | What user sees |
| --- | --- | --- | --- | --- | --- |
| `intake` | describes event | event type, city or audience can be partial | `clarifying` | `update_brief` | brief panel opens with known fields |
| `clarifying` | provides date, budget, venue or concept | enough facts for planning, not necessarily complete | `service_planning` | `update_brief` | brief panel updates and asks next 1-3 questions |
| `service_planning` | says `подбери`, `найди`, `посмотри` | service category or inferred service need | `supplier_searching` | `search_items` | candidate groups appear |
| `supplier_searching` | says `добавь второй` | `visible_candidates` contains ordinal and item id | `supplier_searching` | `select_item` | selected item list updates |
| `supplier_searching` | says `проверь найденных подрядчиков` | selected ids, candidate ids, visible candidates or explicit item ids | `supplier_verification` | `verify_supplier_status` | verification panel/status appears |
| `supplier_verification` | says `сформируй бриф` | non-empty brief exists | `brief_rendered` | `render_event_brief` | structured final brief appears |

Important distinction:

```text
service inference != catalog search
```

For example, `площадка без подвеса` can suggest ground support and floor lighting, but the UI should not show catalog cards until search actually runs.

### 1. Intake

Input example:

```text
Нужно организовать корпоратив на 120 человек в Екатеринбурге.
```

Expected behavior:

- create or update `BriefState`;
- detect event type, city and audience size;
- do not search the entire catalog automatically;
- ask the highest-value next questions.

Assistant message pattern:

```text
Понял, начинаю собирать бриф мероприятия. Уже зафиксировал: корпоратив, Екатеринбург, 120 гостей.

Чтобы двигаться дальше, уточните дату или период, есть ли уже площадка, и какой ориентир по бюджету или уровню мероприятия.
```

State outcome:

```json
{
  "workflow_stage": "clarifying",
  "brief": {
    "event_type": "корпоратив",
    "city": "Екатеринбург",
    "audience_size": 120
  },
  "found_items": []
}
```

### 2. Slot Filling

Input example:

```text
Площадка уже есть, монтаж только ночью, бюджет около 2 млн.
```

Expected behavior:

- update venue status;
- add technical timing constraint;
- set `budget_total`;
- ask concept/date/service-block questions if still missing;
- do not invent services unless policy suggests them as `nice_to_have_services`.

### 3. Service Inference

Input example:

```text
Площадка без подвеса, нужен корпоратив на 300 человек.
```

Expected behavior:

- add `venue_constraints=["площадка без подвеса"]`;
- infer planning implications:
  - lighting should consider stands, floor fixtures or ground support;
  - staging should consider structures that do not require rigging;
  - multimedia should consider floor-mounted or self-supported screens;
- do not claim any supplier can satisfy the constraint until search results are returned.

### 4. Catalog Search

Input example:

```text
Подбери кейтеринг и свет на 120 человек в Екатеринбурге.
```

Expected behavior:

- build at least two `search_requests`;
- execute up to the backend cap;
- return candidates grouped by service category;
- keep `message` as explanation and `found_items` as evidence.

Expected search plan:

```json
[
  {
    "service_category": "кейтеринг",
    "query": "кейтеринг фуршет корпоратив 120 человек Екатеринбург",
    "priority": 1
  },
  {
    "service_category": "свет",
    "query": "световое оборудование корпоратив 120 человек Екатеринбург",
    "priority": 2
  }
]
```

### 4B. Chat-Only Catalog Search

Input example:

```text
Найди подрядчика по свету в Екатеринбурге.
```

Expected behavior:

- set `interface_mode = "chat_search"`;
- do not show the draft brief panel;
- extract service category and city into the search plan;
- ask only search-specific clarifications if the query is too broad;
- after search, render the returned `found_items` as inline catalog cards inside the chat timeline.

Assistant message pattern before search when required data is missing:

```text
Уточните, пожалуйста, город и примерный формат задачи по свету: оборудование, монтаж или операторская работа.
```

Assistant message pattern after search:

```text
Нашёл варианты в каталоге. Карточки ниже — это предварительная выдача по вашему запросу.
```

The message must not open an event brief or ask full event-intake questions unless the user explicitly changes the flow:

```text
Сохрани это в бриф мероприятия.
Давай соберём мероприятие под этих подрядчиков.
```

### 5. Selection

Input example:

```text
Добавь в подборку второй вариант.
```

Expected behavior:

- resolve ordinal only through `visible_candidates`;
- append resolved item id to `selected_item_ids`;
- do not search catalog;
- if `visible_candidates` is absent, ask which item the user means.

### 6. Supplier Verification

Input example:

```text
Проверь найденных подрядчиков.
```

Expected behavior:

- verify suppliers with INN through `verify_supplier_status` only when targets are resolved from `selected_item_ids`, `candidate_item_ids`, `visible_candidates` or explicit item ids;
- ask a clarification if the user says `найденных`, but the request has no candidate context;
- mark suppliers without INN as `not_verified` with `supplier_inn_missing`;
- dedupe verification by `supplier_inn` and map one result to related item ids;
- include verification results separately from assistant prose;
- if external adapter is not configured, return manual `not_verified` results.

Assistant message pattern:

```text
Проверил тех кандидатов, где в каталоге есть ИНН. По позициям без ИНН нужна ручная проверка.
```

The message must not say "подрядчик активен" unless a verification result says `status=active`. Even then, it must describe registry/legal status only, not event-date availability, recommendation or contract validity.

### 7. Final Brief

Input example:

```text
Сформируй итоговый бриф.
```

Expected behavior:

- render structured `RenderedEventBrief`;
- include selected candidates only when selected item ids exist;
- if no items are selected, show found rows only as `кандидаты найдены, но не выбраны`;
- do not calculate budget notes from `found_items` unless selected item ids, quantities and real prices are present;
- include supplier verification summary only from verification results;
- keep missing facts in "Open questions".

Brief sections:

```text
1. Основная информация
2. Концепция и уровень
3. Площадка и ограничения
4. Блоки услуг
5. Подборка кандидатов
6. Проверка подрядчиков
7. Бюджетные заметки
8. Открытые вопросы
```

## Response Policy

`ResponseComposer` should follow this order:

1. Confirm the work state in one sentence.
2. Mention brief updates when they happened.
3. Mention searches, verification or render actions when they ran.
4. Point to evidence-backed UI sections instead of restating catalog facts.
5. Ask 1-3 next questions.

Mode-specific rules:

- In `brief_workspace`, mention what changed in the brief and point the user to the draft brief panel.
- In `chat_search`, keep the answer compact, ask only search clarifications, and place catalog cards directly below the assistant message.
- Do not say "обновил бриф" or show draft brief UI in `chat_search` unless the user explicitly asks to create or save an event brief.

Safe phrasing:

```text
Нашёл кандидатов в каталоге.
Позиции ниже — предварительная подборка.
По части поставщиков нужна ручная проверка, потому что в строках нет ИНН.
```

Unsafe phrasing:

```text
Этот поставщик точно доступен на дату.
Это лучший вариант.
Цена будет такой-то.
Подрядчик работает, хотя verification_results нет.
```

## Response Contract Examples

### Verification With Candidate Context

```json
{
  "message": "Проверил кандидатов, где есть ИНН. По остальным нужна ручная проверка.",
  "ui_mode": "brief_workspace",
  "brief": {},
  "found_items": [],
  "verification_results": [
    {
      "item_id": "uuid",
      "supplier_inn": "7700000000",
      "status": "not_verified",
      "source": "manual_not_verified",
      "risk_flags": ["verification_adapter_not_configured"]
    }
  ],
  "rendered_brief": null
}
```

### Verification Without Candidate Context

```json
{
  "message": "Уточните, каких кандидатов проверить: выберите позиции из выдачи или отправьте их в подборку.",
  "ui_mode": "chat_search",
  "brief": {},
  "found_items": [],
  "verification_results": [],
  "rendered_brief": null
}
```

### Rendered Brief

```json
{
  "message": "Подготовил структурированный бриф. Открытые вопросы оставил отдельным разделом.",
  "ui_mode": "brief_workspace",
  "found_items": [],
  "verification_results": [],
  "rendered_brief": {
    "title": "Бриф мероприятия",
    "sections": [
      {
        "title": "Основная информация",
        "items": ["Тип: корпоратив", "Город: Екатеринбург"]
      },
      {
        "title": "Подборка кандидатов",
        "items": ["Кандидаты найдены, но ещё не выбраны"]
      }
    ],
    "open_questions": ["Дата мероприятия"]
  }
}
```

## Scenario Acceptance Tests

### Intake Case

Input:

```text
Нужно организовать корпоратив на 120 человек в Екатеринбурге.
```

Expected:

- `brief.event_type = "корпоратив"`;
- `brief.city = "Екатеринбург"`;
- `brief.audience_size = 120`;
- `interface_mode = "brief_workspace"`;
- `workflow_stage = "clarifying"`;
- no catalog search unless the user asked for services;
- questions include date/period, venue status and budget or concept.

### Direct Search Case

Input:

```text
Найди подрядчика по свету в Екатеринбурге.
```

Expected:

- `interface_mode = "chat_search"`;
- no draft brief panel is shown;
- `search_requests[0].service_category = "свет"`;
- city is used in the query or normalized search filters when supported;
- clarifications are limited to search quality, not full event-intake questions;
- `found_items` are rendered as inline chat cards.

### Mixed Search Case

Input:

```text
На 120 человек в Екатеринбурге нужен кейтеринг до 2500 на гостя.
```

Expected:

- `interface_mode = "brief_workspace"` when the active context is event creation, otherwise `chat_search`;
- `budget_per_guest = 2500`;
- `required_services` includes `кейтеринг`;
- `workflow_stage = "supplier_searching"`;
- search request category is `кейтеринг`;
- filter includes Екатеринбург when normalized city filter is supported.

### Venue Constraint Case

Input:

```text
Добавь, что площадка без подвеса, и посмотри фермы.
```

Expected:

- `venue_constraints` includes `площадка без подвеса`;
- search categories include `сценические конструкции` and possibly `свет`;
- message explains planning consequence without claiming supplier capability.

### Venue Constraint Without Search Case

Input:

```text
Площадка без подвеса, нужен корпоратив на 300 человек.
```

Expected:

- `venue_constraints` includes `площадка без подвеса`;
- `service_needs` may include policy suggestions for `свет`, `сценические конструкции` or `мультимедиа`;
- `tool_intents` does not include `search_items` unless the user explicitly asked to search;
- UI shows planning implications, not catalog cards.

### Verification Case

Input:

```text
Проверь найденных подрядчиков.
```

Expected:

- verification tool runs only when selected ids, candidate ids, visible candidates or explicit item ids are present;
- verification tool runs for candidates with supplier INN;
- candidates without supplier INN are marked `not_verified`;
- repeated supplier INN is checked once and mapped to related item ids;
- `verification_results` is returned separately;
- message does not invent registry status;
- `status=active` is described as registry/legal status only, not availability, recommendation or contract validity.

### Verification Without Context Case

Input:

```text
Проверь найденных подрядчиков.
```

Request context:

```json
{
  "selected_item_ids": [],
  "candidate_item_ids": [],
  "visible_candidates": []
}
```

Expected:

- `tool_intents` does not include `verify_supplier_status`;
- `verification_results = []`;
- assistant asks which candidates to verify;
- no supplier status is invented.

### Render Brief Case

Input:

```text
Сформируй итоговый бриф.
```

Expected:

- `rendered_brief` is returned;
- sections include event info, services, candidates, verification and open questions;
- selected catalog facts are backed by selected/found/detail rows;
- if `selected_item_ids` is empty, found candidates are labeled as found but not selected;
- budget notes do not treat `found_items` as an estimate without selected rows and explicit quantities;
- unknowns remain open questions.

## Out Of Scope For The First Implementation

- An autonomous multi-turn agent loop.
- Direct SQL, HTTP or browser actions selected by the LLM.
- Automatic CSV supplier-to-contractor resolution during import.
- Automatic final proposal generation with invented quantities.
- Full hybrid sparse+dense ranking, RRF or trigram tuning before regression data shows a need.
- LLM-generated final prose that includes catalog facts.

## Done Criteria

- A manager can start from a plain event request and see a draft brief grow in structured state.
- A manager can also run a direct contractor/service search without opening the brief workspace.
- The assistant can translate brief constraints into service search groups.
- Catalog candidates are returned as evidence-backed `found_items`.
- Candidate references such as `второй вариант` and `найденных подрядчиков` require explicit UI context.
- Supplier verification has an explicit result model, including the unverified state.
- Found candidates are never treated as selected candidates without `selected_item_ids`.
- The final event brief can be rendered as a structured artifact with open questions.
- The UX keeps chat prose, brief state, catalog evidence and verification evidence visually and structurally separate.
