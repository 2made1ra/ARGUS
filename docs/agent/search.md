# Search

ARGUS now has two search flows:

1. Catalog-first MVP search for event agency managers.
2. Existing document drill-down search/RAG for uploaded PDFs/contracts.

Catalog search is the primary MVP user flow. Document search remains available
but must not replace catalog item cards/table.

## Assistant Catalog Search

The assistant has two primary UX modes. The backend returns the mode explicitly
as `ui_mode`; the frontend must not infer it only from text.

```text
brief_workspace
  user explicitly creates, prepares, plans, organizes or renders an event
  -> chat + draft brief + service groups + catalog candidates
     + supplier verification + final brief

chat_search
  user only asks for a contractor, supplier, item, service or price row
  -> simple chat with search clarifications and inline catalog cards
```

The brief workspace opens for event-creation messages such as:

```text
Нужно организовать корпоратив на 120 человек в Екатеринбурге
Собери бриф на конференцию
Готовим презентацию продукта, нужна площадка и подрядчики
```

The chat-only search flow stays active for direct catalog search messages such
as:

```text
Найди подрядчика по свету в Екатеринбурге
Есть кейтеринг до 2500 на гостя?
Покажи радиомикрофоны у поставщиков с НДС
```

Primary backend path:

```text
POST /assistant/chat
  -> ChatTurnUseCase
      -> EventBriefInterpreter
      -> BriefWorkflowPolicy
      -> ToolExecutor
      -> ResponseComposer
  -> response:
      message + ui_mode + router + action_plan + brief
      + found_items + verification_results + rendered_brief
```

Response layers:

```text
message               live explanation, grouping, clarifying questions, next step
ui_mode               brief_workspace | chat_search
router                structured interpretation/debug payload
action_plan           approved tool intents and skipped action reasons
brief                 structured event BriefState
found_items           checkable Postgres price_items rows
verification_results  explicit supplier verification tool output
rendered_brief        deterministic final event brief when requested
```

`message` is not the source of truth for catalog facts. Prices, units,
suppliers, cities, INNs, emails, phones, categories, source text, legal statuses
and date availability must be backed by `found_items`, opened catalog item
details or `verification_results`.

`found_items` are candidates for review, not selected budget/proposal lines.
They become selected only through explicit `selected_item_ids`.

Minimum `found_items` card fields:

```text
id
score
name
category
unit
unit_price
supplier
supplier_city
source_text_snippet
source_text_full_available
match_reason
```

`match_reason` is backend-generated, not free-form LLM prose. Use safe reason
codes/templates such as `semantic`, `keyword_name`, `keyword_supplier`,
`keyword_inn`, `keyword_source_text` and `keyword_external_id`.

`POST /assistant/chat` request:

```json
{
  "session_id": null,
  "message": "Нужно организовать корпоратив на 120 человек в Екатеринбурге",
  "brief": {
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
    "budget_total": null,
    "budget_per_guest": null,
    "budget_notes": null,
    "event_level": null,
    "service_needs": [],
    "required_services": [],
    "must_have_services": [],
    "nice_to_have_services": [],
    "selected_item_ids": [],
    "constraints": [],
    "preferences": [],
    "open_questions": []
  },
  "recent_turns": [],
  "visible_candidates": [],
  "candidate_item_ids": []
}
```

Response:

```json
{
  "session_id": "uuid",
  "message": "Понял, начинаю собирать бриф мероприятия. Уже зафиксировал: корпоратив, Екатеринбург, 120 гостей. Уточните дату или период, есть ли уже площадка, и какой ориентир по бюджету или уровню мероприятия.",
  "ui_mode": "brief_workspace",
  "router": {
    "interface_mode": "brief_workspace",
    "intent": "brief_discovery",
    "workflow_stage": "clarifying",
    "confidence": 0.88,
    "reason_codes": ["event_creation_intent_detected", "brief_update_detected"],
    "brief_update": {
      "event_type": "корпоратив",
      "city": "Екатеринбург",
      "audience_size": 120
    },
    "search_requests": [],
    "tool_intents": ["update_brief"],
    "should_search_now": false,
    "missing_fields": ["date_or_period", "venue_status", "budget_total"],
    "clarification_questions": [
      "На какую дату или период планируется мероприятие?",
      "Площадка уже есть или ее нужно подобрать?",
      "Какой ориентир по бюджету или уровню мероприятия?"
    ]
  },
  "action_plan": {
    "interface_mode": "brief_workspace",
    "workflow_stage": "clarifying",
    "tool_intents": ["update_brief"],
    "search_requests": [],
    "verification_targets": [],
    "render_requested": false
  },
  "brief": {
    "event_type": "корпоратив",
    "city": "Екатеринбург",
    "date_or_period": null,
    "audience_size": 120,
    "open_questions": [
      "date_or_period",
      "venue_status",
      "budget_total",
      "concept"
    ]
  },
  "found_items": [],
  "verification_results": [],
  "rendered_brief": null
}
```

Direct chat-search response example:

```json
{
  "session_id": "uuid",
  "message": "Нашел варианты в каталоге. Карточки ниже - предварительная выдача по вашему запросу.",
  "ui_mode": "chat_search",
  "router": {
    "interface_mode": "chat_search",
    "intent": "supplier_search",
    "workflow_stage": "searching",
    "reason_codes": ["direct_catalog_search_detected", "service_need_detected"],
    "search_requests": [
      {
        "query": "световое оборудование Екатеринбург",
        "service_category": "свет",
        "filters": {
          "supplier_city_normalized": "екатеринбург"
        },
        "priority": 1,
        "limit": 8
      }
    ],
    "should_search_now": true
  },
  "brief": {},
  "found_items": [],
  "verification_results": [],
  "rendered_brief": null
}
```

Assistant implementation boundaries:

- `assistant` owns `BriefState`, structured interpretation, workflow policy,
  response composition and chat turn orchestration.
- `assistant` calls catalog search through an explicit search-items port.
- HTTP composition may adapt the catalog use case into that port; assistant
  feature code must not import catalog internals directly.
- Document RAG is not a fallback for catalog prices, suppliers or item evidence.
- LLM output can help produce structured interpretation, but backend policy
  validates and authorizes every tool call.
- One chat turn is bounded. Do not add a recursive agent loop.
- Phrases such as `второй вариант`, `первые два` and
  `проверь найденных подрядчиков` require explicit request context through
  `visible_candidates`, `candidate_item_ids` or `selected_item_ids`; do not
  resolve them from hidden server memory.

## `search_items`

Catalog search tool behavior:

```text
1. Embed user query as catalog_query_prefix + query.
   Default catalog_query_prefix is "search_query: ".
2. Search Qdrant collection price_items_search_v1 with simple payload filters.
3. Run minimal Postgres keyword fallback for exact supplier/name/INN/source text
   and external_id style searches.
4. Merge and dedupe candidate price_item_id values, preserving semantic ranking
   first and appending keyword-only matches.
5. Hydrate rows from Postgres price_items, which remains the source of truth.
6. Return item cards with source_text_snippet and backend match_reason.
```

The catalog item embedding indexed in Qdrant is generated from
`"search_document: " + price_items.embedding_text`.

`POST /catalog/search` exposes the same tool-friendly contract for debugging,
admin use and future assistant orchestration:

```json
{
  "query": "аренда звукового оборудования",
  "limit": 10,
  "filters": {
    "supplier_city": "г. Москва",
    "category": "Аренда",
    "supplier_status": "Активен",
    "has_vat": "Без НДС",
    "unit_price": "15000.00"
  }
}
```

Response:

```json
{
  "items": [
    {
      "id": "uuid",
      "score": 0.82,
      "name": "Аренда акустической системы",
      "category": "Аренда",
      "unit": "день",
      "unit_price": "15000.00",
      "supplier": "ООО Пример",
      "supplier_city": "г. Москва",
      "source_text_snippet": "фрагмент исходной строки",
      "source_text_full_available": true,
      "match_reason": {
        "code": "semantic",
        "label": "Семантическое совпадение с запросом"
      }
    }
  ]
}
```

Keyword fallback is part of MVP because managers will search for exact supplier
names, INNs, service names, equipment models and external CSV ids. This is not a
full hybrid sparse+dense ranking system; sparse vectors, RRF, trigram tuning and
metric-driven reranking are post-MVP.

Search result evidence rules:

- Primary catalog result is a cards/table view hydrated from Postgres.
- Assistant prose may explain and group results, but must not replace the
  checkable rows.
- Empty results should say the catalog has no matching rows and suggest a
  refined query or missing filters.
- Empty backend search returns `"items": []`; it must not fabricate catalog
  cards or prose-only substitutes.
- Do not use CSV legacy embeddings for user query search.
- Do not search document chunks as catalog evidence for prices/suppliers.

## Brief State

The event-brief workspace stores one active `BriefState` per request/session
context. The first implementation can remain stateless on the backend side and
receive the current brief from the frontend.

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
  "event_level": null,
  "constraints": [],
  "preferences": [],
  "open_questions": []
}
```

Brief is state, not a prose-only summary. A final prose brief can be rendered
from `BriefState`, selected catalog rows and supplier verification results.

Service field semantics:

- `service_needs` is the normalized model used by policy and search planning.
- `required_services` is a compatibility/UI projection of explicitly requested
  service blocks.
- `must_have_services` contains explicitly mandatory service blocks only.
- `nice_to_have_services` contains policy suggestions and must never be treated
  as selected or mandatory.
- `technical_requirements` contains execution requirements, not service
  categories.
- `venue_constraints` contains constraints caused by the venue only.
- `selected_item_ids` contains explicit user choices. `found_items` must not be
  copied into it automatically.

Budget fields stay separate: total budget, per-guest budget and uncertain
budget notes are different facts.

## Three-level drill-down

```
GET /search?q=поставщики+фруктов
    → search_contractors: global semantic search, aggregate by contractor_entity_id
    → [{contractor_id, name, score, matched_chunks_count, top_snippet}]

GET /contractors/{id}/search?q=штрафы
    → search_documents: filter by contractor_entity_id
    → [{document_id, title, date, matched_chunks: [{page, snippet}]}]

GET /documents/{id}/search?q=риски
    → search_within_document: filter by document_id
    → [{chunk_index, page_start, page_end, section_type, snippet, score}]
```

## Qdrant filter patterns

```python
# Level 1 — global (no filter)
qdrant.search(embedding, limit=200)
# aggregate by contractor_entity_id in Python
# Prefer Qdrant Group By API: group_by="contractor_entity_id"

# Level 2 — by contractor
Filter(must=[FieldCondition("contractor_entity_id", MatchValue(id))])

# Level 3 — inside document
Filter(must=[FieldCondition("document_id", MatchValue(id))])
```

## Document Search Rules

- For document drill-down endpoints, use one vector search per call, filtered.
- Search use cases combine Qdrant (semantic) + Postgres (metadata: title, date, contractor name).
- `is_summary: true` chunks are included in global search; filter them out when searching within a document if needed.
- These rules do not override the catalog `search_items` MVP behavior, which may
  combine Qdrant semantic search with minimal Postgres keyword fallback.

## RAG / Answer endpoints

All answer endpoints accept `POST` with body:
```json
{ "message": "string", "history": [{"role": "user|assistant", "content": "string"}], "limit": 10 }
```

**Per-document:** `POST /documents/{id}/answer`
- Scoped to one document's chunks + extracted facts.
- Returns `{ answer, sources: [{ document_id, contractor_id, page_start, page_end, chunk_index, score, snippet, document_title, contractor_name }] }`

**Per-contractor:** `POST /contractors/{id}/answer`
- Scoped to all documents linked to the contractor.
- Returns same shape as per-document.

**Global:** `POST /search/answer`
- RAG across all indexed documents, supports multi-turn via `history`.
- Returns `{ answer, contractors: [...], sources: [...] }`

## SSE status stream

```
GET /documents/{id}/stream  →  text/event-stream
```

Polls document status every ~1 s, yields on each status transition, closes on
`INDEXED` or `FAILED`. On `FAILED`, adds `"error_message"` to the event payload.

```
data: {"document_id": "uuid", "status": "PROCESSING"}\n\n
data: {"document_id": "uuid", "status": "INDEXED"}\n\n
```
