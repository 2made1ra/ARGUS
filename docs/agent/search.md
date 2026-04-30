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
