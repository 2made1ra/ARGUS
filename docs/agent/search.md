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

## `search_items`

Catalog search tool behavior:

```text
1. Embed user query as "search_query: " + query.
2. Search Qdrant collection price_items_search_v1 with simple payload filters.
3. Run minimal Postgres keyword fallback for exact supplier/name/INN/source text
   and external_id style searches.
4. Merge and dedupe candidate price_item_id values.
5. Hydrate rows from Postgres price_items.
6. Return item cards with source_text_snippet and backend match_reason.
```

The catalog item embedding indexed in Qdrant is generated from
`"search_document: " + price_items.embedding_text`.

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
