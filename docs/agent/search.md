# Search

ARGUS now has two search flows:

1. Catalog-first MVP search for event agency managers.
2. Existing document drill-down search/RAG for uploaded PDFs/contracts.

Catalog search is the primary MVP user flow. Document search remains available
but must not replace catalog item cards/table.

## Catalog Assistant Search

Primary user path:

```text
POST /assistant/chat
  -> router: brief_discovery | supplier_search | mixed | clarification
  -> brief merge
  -> search_items when useful
  -> response: message + router + brief + found_items
```

Response layers:

```text
message      live explanation, grouping, clarifying questions, next step
router       structured routing decision for observability/debugging
brief        structured event BriefState
found_items  checkable Postgres price_items rows
```

`message` is not the source of truth for catalog facts. Prices, units,
suppliers, cities, INNs, emails, phones, categories, source text and date
availability must be backed by `found_items` or an opened catalog item detail.
For catalog search turns the assistant may explain what happened and suggest
next refinements, but concrete catalog rows must stay in `found_items`.
`found_items` are candidates for review, not selected budget/proposal lines.

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
  "message": "Организовать музыкальный вечер на 100 человек",
  "brief": {
    "event_type": null,
    "city": null,
    "date_or_period": null,
    "audience_size": null,
    "venue": null,
    "venue_status": null,
    "duration_or_time_window": null,
    "budget": null,
    "event_level": null,
    "required_services": [],
    "constraints": [],
    "preferences": []
  }
}
```

Response:

```json
{
  "session_id": "uuid",
  "message": "Обновил черновик брифа и запустил поиск по очевидной потребности. Проверяемые карточки находятся в found_items; это кандидаты, а не готовые строки коммерческого предложения.",
  "router": {
    "intent": "mixed",
    "confidence": 0.88,
    "known_facts": {
      "event_type": "музыкальный вечер",
      "audience_size": 100
    },
    "missing_fields": ["city", "venue_status"],
    "should_search_now": true,
    "search_query": "музыкальное оборудование для музыкального вечера на 100 человек",
    "brief_update": {
      "event_type": "музыкальный вечер",
      "city": null,
      "date_or_period": null,
      "audience_size": 100,
      "venue": null,
      "venue_status": null,
      "duration_or_time_window": null,
      "budget": null,
      "event_level": null,
      "required_services": ["звук"],
      "constraints": [],
      "preferences": []
    }
  },
  "brief": {
    "event_type": "музыкальный вечер",
    "city": null,
    "date_or_period": null,
    "audience_size": 100,
    "venue": null,
    "venue_status": null,
    "duration_or_time_window": null,
    "budget": null,
    "event_level": null,
    "required_services": ["звук"],
    "constraints": [],
    "preferences": []
  },
  "found_items": []
}
```

Assistant implementation boundaries:

- `assistant` owns `BriefState`, router decisions and chat turn orchestration.
- `assistant` calls catalog search through an explicit search-items port.
- HTTP composition may adapt the catalog use case into that port; assistant
  feature code must not import catalog internals directly.
- Document RAG is not a fallback for catalog prices, suppliers or item evidence.

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

MVP stores one active brief per chat/session:

```json
{
  "event_type": null,
  "city": null,
  "date_or_period": null,
  "audience_size": null,
  "venue": null,
  "venue_status": null,
  "duration_or_time_window": null,
  "budget": null,
  "event_level": null,
  "required_services": [],
  "constraints": [],
  "preferences": []
}
```

Brief is state, not a prose-only summary. A final prose brief can be rendered
from `BriefState` and selected/found catalog rows, but final commercial proposal
generation is post-MVP.

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
