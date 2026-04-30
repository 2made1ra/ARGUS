# Ingestion Pipeline & Celery Chain

## 14-step ingestion workflow

```
1.  POST /documents/upload
2.  upload_document use case:
        stores file to disk, creates Document(status=QUEUED)
        enqueues Celery task: process_document

3.  Celery task: process_document
        document.status = PROCESSING
        result = await sage.process_document(file_path)
            ├── ensure_pdf (LibreOffice if not PDF)
            ├── detect_kind → TEXT or SCAN
            ├── extract_text_pages / ocr_pages
            ├── normalize_text
            ├── chunk (pages + headings + semantic)
            ├── LLM: extract_one per chunk → merge_fields (left-prefer)
            └── LLM: summarize (map-reduce per-page → reduce)

4.  Store to Postgres:
        document_chunks, extracted_fields, document_summaries
        document.partial_extraction = result.partial

5.  Celery chain → resolve_contractor task
        document.status = RESOLVING
        → see docs/agent/entity-resolution.md
        document.contractor_entity_id = resolved_id

6.  Celery chain → index_document task
        document.status = INDEXING
        for chunk in document_chunks:
            vector = await embedding_service.embed(chunk.text)
            qdrant.upsert(vector, payload)
        # also index document-level summary (is_summary=True)
        document.status = INDEXED
```

## Document status lifecycle

```
QUEUED → PROCESSING → RESOLVING → INDEXING → INDEXED
                                             ↘ FAILED (any stage)
```

`document.status` is the single source of truth — used by SSE and polling.
Failures set `documents.error_message` with the reason.

## Celery setup

Tasks are thin: call use case → chain next task → no business logic.

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_document(self, document_id: str) -> None:
    run_async(ProcessDocumentUseCase(...).execute(DocumentId(document_id)))
    resolve_contractor.apply_async(args=[document_id])

@celery_app.task(bind=True, max_retries=3)
def resolve_contractor(self, document_id: str) -> None:
    run_async(ResolveContractorUseCase(...).execute(DocumentId(document_id)))
    index_document.apply_async(args=[document_id])

@celery_app.task(bind=True, max_retries=3)
def index_document(self, document_id: str) -> None:
    run_async(IndexDocumentUseCase(...).execute(DocumentId(document_id)))
```

`run_async()` is a thin bridge: `asyncio.get_event_loop().run_until_complete(coro)`.
Task chaining is explicit — no EventBus, no domain events infrastructure.

## SSE status stream

```
GET /documents/{id}/stream  →  text/event-stream

data: {"status": "PROCESSING", "document_id": "uuid"}\n\n
data: {"status": "RESOLVING",  "document_id": "uuid"}\n\n
data: {"status": "INDEXED",    "document_id": "uuid"}\n\n
```

FastAPI `StreamingResponse` polls `document.status` from DB every ~1 s,
yields on change, closes on `INDEXED` or `FAILED`.
