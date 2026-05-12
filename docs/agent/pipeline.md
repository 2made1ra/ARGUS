# Ingestion Pipeline & Celery Chain

ARGUS has two ingestion paths:

- Catalog MVP path: `prices.csv -> price_items -> price_items_search_v1`.
- Existing document path: PDF/contract upload through SAGE and Celery.

The document path remains available and unchanged during catalog MVP work.
PDF-to-catalog extraction is post-MVP and must not block CSV import/search/chat.

The event-brief assistant is an application workflow over catalog search and
supplier verification tools. It is not part of the document Celery chain and
must not change document statuses.

## Catalog import/index path

Catalog import is not part of the document Celery chain:

```text
POST /catalog/imports
  -> store price_imports + price_import_rows
  -> normalize CSV-compatible fields
  -> build deterministic embedding_text prices_v1
  -> upsert active price_items in Postgres
  -> IndexPriceItemsUseCase:
       embed "search_document: " + embedding_text
       validate configured catalog dimension
       upsert Qdrant price_items_search_v1
       set catalog_index_status = indexed | embedding_failed | indexing_failed
```

Guidance:

- Prefer generate+index as one MVP flow unless generated vectors are explicitly
  persisted in a separate storage contract.
- `embedding_failed` and `indexing_failed` are different states and should keep
  separate error messages.
- Use `file_sha256` and/or `row_fingerprint` to prevent accidental duplicate
  active rows on repeated CSV imports.
- CSV legacy `embedding` is audit-only and never a catalog query search vector.
- Do not infer catalog embedding dimension from legacy CSV vectors.

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

Do not add catalog-specific statuses to `documents.status`. Catalog import and
catalog indexing use their own import/index status fields.

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

## Post-MVP PDF-to-catalog extraction

After CSV import, catalog search and unified chat are stable, SAGE may add a
`PriceItemExtraction[]` output. Those extracted rows must still flow through the
same catalog contract:

```text
PDF upload
  -> existing document lifecycle
  -> optional PriceItemExtraction[]
  -> catalog normalization
  -> price_items
  -> embedding_text prices_v1
  -> price_items_search_v1
  -> assistant found_items cards
```

Document chunks and summaries can support document RAG, but they must not become
the main proof for catalog facts such as price, supplier, unit or city. If a PDF
contains catalog-worthy rows, first normalize them into `price_items` with
document/page/chunk provenance.

## Assistant Tool Boundary

`POST /assistant/chat` may call catalog and verification tools during one
bounded chat turn:

```text
ChatTurnUseCase
  -> EventBriefInterpreter
  -> BriefWorkflowPolicy
  -> ToolExecutor
       -> update_brief
       -> search_items
       -> get_item_details
       -> verify_supplier_status
       -> render_event_brief
```

These calls are synchronous application/use-case orchestration unless a future
task explicitly introduces background work. They must not enqueue document
pipeline tasks, change `documents.status`, or use document chunks as catalog
evidence.

## SSE status stream

```
GET /documents/{id}/stream  →  text/event-stream

data: {"status": "PROCESSING", "document_id": "uuid"}\n\n
data: {"status": "RESOLVING",  "document_id": "uuid"}\n\n
data: {"status": "INDEXED",    "document_id": "uuid"}\n\n
```

FastAPI `StreamingResponse` polls `document.status` from DB every ~1 s,
yields on change, closes on `INDEXED` or `FAILED`.
