# Search — Drill-down UX

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

## Rules

- One vector search per call, filtered — no multiple search strategies per request.
- Search use cases combine Qdrant (semantic) + Postgres (metadata: title, date, contractor name).
- `is_summary: true` chunks are included in global search; filter them out when searching within a document if needed.

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
