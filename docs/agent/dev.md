# Development Workflow

## Prerequisites

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- Docker + Docker Compose
- Node.js 18+ (for the frontend only)

## Environment setup

Copy `.env.example` → `.env` in the repo root:

```
DATABASE_URL=postgresql+asyncpg://argus:argus@localhost:5432/argus
ALEMBIC_DATABASE_URL=postgresql+asyncpg://argus:argus@localhost:5432/argus
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
LM_STUDIO_URL=http://localhost:1234/v1
LM_STUDIO_EMBEDDING_MODEL=nomic-embed-text-v1.5
LM_STUDIO_LLM_MODEL=<your model name>
```

Settings are loaded by `backend/app/config.py` via `pydantic-settings`.
`ALEMBIC_DATABASE_URL` is read separately by Alembic via `alembic.ini`.

Catalog MVP settings should split document and catalog vector configuration when
implemented:

```text
DOCUMENT_QDRANT_COLLECTION=document_chunks
CATALOG_QDRANT_COLLECTION=price_items_search_v1
CATALOG_EMBEDDING_MODEL=nomic-embed-text-v1.5
CATALOG_EMBEDDING_DIM=768
CATALOG_EMBEDDING_TEMPLATE_VERSION=prices_v1
CATALOG_DOCUMENT_PREFIX="search_document: "
CATALOG_QUERY_PREFIX="search_query: "
```

Do not copy catalog dimension from CSV legacy embeddings. For
`nomic-embed-text-v1.5`, catalog rows are embedded with `search_document: ` and
user queries with `search_query: `. A prefix/model/dimension/template change
requires reindexing `price_items_search_v1`.

## uv workspace

The repo root is a uv workspace with two members:

```
backend/        → argus-backend (app/)
packages/sage   → sage package (sage/)
```

Run `uv sync` from the repo root to install everything. The backend depends on `sage`
via a workspace reference — no separate install needed.

## Infrastructure

```bash
make infra-up     # Start Postgres 16, Redis 7, Qdrant (detached)
make infra-down   # Stop containers (data volumes persist)
make infra-logs   # Tail logs
make infra-ps     # Show container status
```

Docker services (no `--profile` flag; started by `make infra-up`):

| Service | Image | Port |
|---------|-------|------|
| postgres | postgres:16 | 5432 |
| redis | redis:7-alpine | 6379 |
| qdrant | qdrant/qdrant:latest | 6333 (HTTP), 6334 (gRPC) |

## Local development (backend)

```bash
make dev      # uvicorn app.main:app --reload on :8000
make worker   # Celery worker (handles ingest tasks)
make migrate  # Alembic upgrade head
```

Start infra before `make dev`. Start the worker before uploading documents.
FastAPI docs: `http://localhost:8000/docs`. OpenAPI spec: `docs/api/openapi.yaml`.

### Database migrations

Three migrations exist:
1. `0001_initial` — all base tables
2. `0002_unique_contractors_inn` — unique constraint on `contractors.inn`
3. `0003_document_preview_file_path` — adds `preview_file_path` to `documents`

Run `make migrate` once after first `infra-up` and after adding new migrations.

## Full Docker stack

```bash
make app-up    # Builds and starts api + celery-worker (--profile app)
make app-down  # Stops api + celery-worker
```

Use `make infra-up` + `make dev` for local development (hot reload).
Use `make app-up` when you want the full stack in Docker (no hot reload).

## OCR (macOS only)

```bash
make install-ocr    # Tesseract + Russian + English language data via Homebrew
make uninstall-ocr  # Remove Tesseract and language data
```

Required for scanned PDFs. The Celery worker uses `pytesseract` which delegates to
the system `tesseract` binary. Skip if only processing digital PDFs.

## Frontend

```bash
cd frontend
npm install       # First time only
npm run dev       # Vite dev server
npm run build     # TypeScript check + production build
```

The frontend is a standalone Vite + React 18 + TypeScript SPA in `frontend/`.
Run it independently from the backend.

## Tests

From the repo root:

```bash
pytest                                          # All tests
pytest backend/tests/features/test_search.py   # Specific file
```

Config in root `pyproject.toml`: `asyncio_mode = "auto"`,
`pythonpath = ["backend", "packages/sage"]`, `testpaths = ["backend/tests"]`.

Catalog-first implementation should prefer focused checks for the changed slice:

```bash
uv run --project backend pytest backend/tests/features/catalog -v
uv run --project backend pytest backend/tests/features/assistant -v
uv run --project backend pytest backend/tests/adapters/qdrant -v
```

Event-brief assistant work should start with deterministic/fake LLM tests and
only use real LM Studio calls for optional integration checks:

```bash
uv run --project backend pytest backend/tests/features/assistant/test_workflow_golden_cases.py -v
uv run --project backend pytest backend/tests/features/assistant/test_event_brief_interpreter.py -v
uv run --project backend pytest backend/tests/features/assistant/test_brief_workflow_policy.py -v
uv run --project backend pytest backend/tests/features/assistant/test_response_composer.py -v
```

Frontend work on the two assistant UX modes should end with:

```bash
cd frontend
npm run build
```

Manual UX checks:

- Explicit event creation opens `brief_workspace`.
- Direct contractor/service search stays in `chat_search`.
- Catalog facts are rendered in item cards, not only in assistant prose.
- `проверь найденных подрядчиков` without `visible_candidates`,
  `candidate_item_ids` or `selected_item_ids` asks clarification.
- Final brief does not treat all `found_items` as selected items.

Document pipeline regressions should remain covered when touching SAGE,
ingestion, document indexing or Qdrant bootstrap:

```bash
uv run --project packages/sage pytest -v
uv run --project backend pytest backend/tests/features/ingest -v
```

## Linting and formatting

```bash
ruff check .         # Lint
ruff check . --fix   # Lint + auto-fix
ruff format .        # Format (line-length 88, target py313)
```

Ruff targets `backend/app`, `backend/tests`, `packages/sage/sage`.
