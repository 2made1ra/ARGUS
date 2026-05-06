# Architecture & Repo Layout

## Pattern: Vertical Slice + Hexagonal Core

```
argus/
├── packages/
│   └── sage/                        # Standalone Python package — document processing
│       └── sage/
│           ├── conversion/          # LibreOffice PDF conversion
│           ├── pdf/                 # detect_kind, extract_text_pages, ocr_pages
│           ├── normalizer/          # Text cleanup
│           ├── chunker/             # Page + heading + semantic chunking
│           ├── llm/                 # LM Studio client + extraction/summary prompts
│           └── models.py            # Page, ExtractedDocument, ContractFields, ProcessingResult
│
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── domain/              # Shared value objects: ContractorEntityId, DocumentId, ChunkId
│   │   │   └── ports/               # Shared Protocol interfaces (UnitOfWork)
│   │   │
│   │   ├── features/
│   │   │   ├── ingest/              # Upload → process → index pipeline
│   │   │   ├── contractors/         # Entity resolution + contractor profiles
│   │   │   ├── search/              # Drill-down semantic search
│   │   │   └── documents/           # Document management + review
│   │   │
│   │   ├── adapters/
│   │   │   ├── sqlalchemy/          # PostgreSQL repos
│   │   │   ├── qdrant/              # Vector index + search
│   │   │   ├── celery/              # Task dispatch
│   │   │   ├── sage/                # Wraps packages/sage into ingest ports
│   │   │   └── llm/                 # LM Studio client
│   │   │
│   │   ├── entrypoints/
│   │   │   ├── http/                # FastAPI routers — one per feature
│   │   │   └── celery/              # Celery task definitions
│   │   │
│   │   └── config.py
│   │
│   ├── migrations/                  # Alembic
│   └── tests/
│
├── frontend/                            # React 18 + Vite + TypeScript SPA
│   └── src/
│
├── docs/
│   └── api/
│       └── openapi.yaml                 # HTTP API contract
│
├── docker-compose.yml
└── CLAUDE.md
```

## Layer rules

- **Features** own their entities, use cases, and ports. Features do not import from each other.
- **Shared types** used by multiple features live in `core/domain/`.
- **Ports** (Protocol interfaces) are defined inside the feature. The adapter implementing them lives in `adapters/`.
- **Use cases** receive all dependencies via constructor injection — no global state, no DI framework.
- **Entrypoints** (HTTP handlers, Celery tasks) only call use cases and map errors. No business logic.
- **Adapters** implement interfaces — they do not own product logic.

## Feature map

| Feature | Responsibility |
|---------|---------------|
| `ingest` | File upload, SAGE processing, chunk/field/summary storage, Celery chain |
| `contractors` | Entity resolution, contractor profiles, raw-to-entity mappings |
| `search` | Drill-down semantic search + RAG answer use cases (global, per-contractor, per-document) |
| `documents` | Document detail, list, extracted facts, PDF preview |

## packages/sage

SAGE is stateless and side-effect-free: receives a file path, returns a `ProcessingResult`.
No database, no HTTP, no Celery. Single public entry point:

```python
from sage import process_document, ProcessingResult
result: ProcessingResult = await process_document(src=Path("contract.docx"), work_dir=tmp)
```

## OpenAPI spec

Live spec is at `docs/api/openapi.yaml`. Use it as the reference for
request/response shapes rather than reading router files directly.

## Tech stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + uvicorn |
| Task queue | Celery + Redis |
| ORM | SQLAlchemy 2.x async + Alembic |
| Database | PostgreSQL |
| Vector DB | Qdrant |
| Document processing | packages/sage (pymupdf, pytesseract, LibreOffice) |
| LLM | LM Studio (local) via OpenAI-compatible API |
| Python | 3.13+ |
