# ARGUS — Architecture Roadmap

Document intelligence platform for contractor management and contract search.
This roadmap is the build plan for taking ARGUS from a greenfield repo (only
`CLAUDE.md` exists today) to a working MVP with end-to-end ingestion, entity
resolution, indexing, drill-down search, and a minimal test frontend.

The companion C4 container diagram lives at `docs/architecture/c4-container.puml`
(placeholder — paste the PlantUML source provided alongside this roadmap).

---

## Architectural premises (recap)

- **Vertical slice + hexagonal core.** `features/` own their entities, use cases,
  and ports. `core/` holds shared types and base ports. `adapters/` implement
  external dependencies. No cross-feature imports.
- **`packages/sage` is stateless.** Single async entry point
  `process_document(src, work_dir) → ProcessingResult`. No DB, no HTTP, no Celery.
  This roadmap **extracts** the pipeline from the existing SAGE service (option **a**)
  and discards SAGE's FastAPI/persistence layers.
- **Task chaining, no domain events.** Celery tasks call use cases and chain the
  next task explicitly. Document `status` is the SSoT for pipeline progress.
- **Single Qdrant collection** `document_chunks`, payload-filtered for drill-down.
- **LLM via LM Studio** (OpenAI-compatible). **Embeddings: `nomic-embed-text-v1.5`**
  served by LM Studio at `${LM_STUDIO_URL}`.
- **Auth, multi-tenancy, observability, CI/CD** are explicitly post-MVP — see
  "Post-MVP" at the bottom.

## Conventions for every PR

- **Size:** small, ~200–400 LOC of meaningful change, one concern.
- **Tests:** unit tests for use cases and pure logic (chunker, normalizer,
  resolver, field merger). Adapter integration tests are post-MVP.
- **Ports are `typing.Protocol`**, defined inside the feature. Adapters live
  in `backend/app/adapters/<tech>/`.
- **Use cases**: dependencies via `__init__`, work via `async def execute(...)`.
  No global state.
- **Entrypoints stay thin.** No business logic in HTTP handlers or Celery tasks.
- **Naming:** `contractor` (never `supplier`), ID newtypes (`DocumentId`,
  `ContractorEntityId`, `ChunkId`), tables plural snake_case.
- **Each PR prompt is self-contained.** It references `CLAUDE.md` and this
  roadmap so it can be run by Claude Code or Codex without prior session context.

---

## Track overview

| # | Track | PRs | Goal |
|---|-------|-----|------|
| 0 | Foundation | 4 | Monorepo skeleton, compose stack, config, diagram placeholder |
| 1 | SAGE package | 8 | Extract `packages/sage` from existing SAGE service |
| 2 | Core domain & ports | 2 | Shared ID types and `UnitOfWork` |
| 3 | Persistence baseline | 3 | SQLAlchemy/Alembic, initial migration, base session/UoW |
| 4 | Ingest feature | 4 | Upload → process → persist chunks/fields/summary |
| 5 | Contractors feature | 3 | Resolution cascade, profile, listing |
| 6 | Indexing | 3 | Qdrant adapter, embedding adapter, `index_document` |
| 7 | Search feature | 3 | Drill-down: contractors → documents → within-document |
| 8 | Documents feature | 1 | Read APIs (get, list, facts) |
| 9 | Celery & HTTP entrypoints | 4 | Celery app, task chain, FastAPI routers, SSE stream |
| 10 | Test frontend | 3 | React+Vite minimal upload + drill-down search UI |

End of Track 10 = MVP. Tracks 0–3 are mostly sequential; 4–9 unlock
incrementally; 10 can start once Track 9's HTTP routes exist.

---

## Track 0 — Foundation

Goal: empty but coherent monorepo that boots dependencies via `docker-compose up`.

### PR 0.1 — Monorepo skeleton

**Files:** `backend/pyproject.toml`, `backend/app/__init__.py`,
`backend/app/{core,features,adapters,entrypoints}/__init__.py`,
`backend/app/{core/{domain,ports},features/{ingest,contractors,search,documents},
adapters/{sqlalchemy,qdrant,celery,sage,llm},entrypoints/{http,celery}}/__init__.py`,
`packages/sage/pyproject.toml`, `packages/sage/sage/__init__.py`, root `README.md`,
`.gitignore`, `.editorconfig`.

**Acceptance:** `pip install -e backend && pip install -e packages/sage` works.
`python -c "import sage; from app import core"` succeeds. No business code yet.

**Prompt:**
> Create the monorepo skeleton for ARGUS as described in `CLAUDE.md` "Repository
> layout". Add `backend/pyproject.toml` (Python 3.12, deps: fastapi, uvicorn,
> sqlalchemy[asyncio], asyncpg, alembic, celery, redis, qdrant-client, httpx,
> rapidfuzz, pydantic, pydantic-settings; dev deps: pytest, pytest-asyncio).
> Add `packages/sage/pyproject.toml` (deps: pymupdf, pytesseract, pillow,
> httpx, pydantic). Create empty `__init__.py` for every package and subpackage
> listed in the layout. Add `.gitignore` (Python, venv, `.env`, `data/`),
> `.editorconfig`, and a short `README.md` pointing to `CLAUDE.md` and
> `ARCHITECTURE_ROADMAP.md`. Do not add business logic.

### PR 0.2 — docker-compose stack

**Files:** `docker-compose.yml`, `backend/Dockerfile`, `.env.example`.

**Acceptance:** `docker-compose up postgres redis qdrant` brings up the three
infra services with healthy ports. `api` and `celery-worker` build (may exit
because no entrypoint code yet — that's fine).

**Prompt:**
> Create `docker-compose.yml` per `CLAUDE.md` "Infrastructure — docker-compose"
> exactly: services `api`, `celery-worker`, `postgres:16`, `redis:7-alpine`,
> `qdrant/qdrant:latest`, named volumes `pg_data` and `qdrant_data`. Add
> `backend/Dockerfile` (python:3.12-slim, install LibreOffice + tesseract-ocr +
> tesseract-ocr-rus, `pip install -e .`). Add `.env.example` with
> `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`, `LM_STUDIO_URL`,
> `LM_STUDIO_EMBEDDING_MODEL=nomic-embed-text-v1.5`, `LM_STUDIO_LLM_MODEL=`
> (blank for the user to fill). Mount `./data/uploads` into both `api` and
> `celery-worker` at `/data/uploads`.

### PR 0.3 — Config

**Files:** `backend/app/config.py`, `backend/tests/test_config.py`.

**Acceptance:** `Settings()` loads from env, fails fast if `DATABASE_URL` or
`LM_STUDIO_URL` missing. Unit test verifies parsing and defaults.

**Prompt:**
> Add `backend/app/config.py` using `pydantic-settings`. Define `Settings` with
> fields: `database_url: str`, `redis_url: str`, `qdrant_url: str`,
> `lm_studio_url: str`, `lm_studio_embedding_model: str =
> "nomic-embed-text-v1.5"`, `lm_studio_llm_model: str`, `upload_dir: Path =
> Path("/data/uploads")`, `qdrant_collection: str = "document_chunks"`,
> `embedding_dim: int = 768` (nomic-embed-text-v1.5 native dim). Provide
> `get_settings()` cached with `lru_cache`. Add a unit test that monkeypatches
> env vars and asserts the parsed values.

### PR 0.4 — Architecture docs placeholder

**Files:** `docs/architecture/c4-container.puml`, `docs/architecture/README.md`.

**Acceptance:** the `.puml` file exists with a TODO placeholder; the
`README.md` explains how to render and references this roadmap.

**Prompt:**
> Create `docs/architecture/c4-container.puml` with a placeholder comment block
> "Paste C4 container diagram source here (see ARCHITECTURE_ROADMAP.md)". Add
> `docs/architecture/README.md` with one short section: how to render the
> diagram (e.g. `plantuml -tsvg c4-container.puml`) and a link back to
> `../../ARCHITECTURE_ROADMAP.md`.

---

## Track 1 — SAGE package extraction

Goal: take the existing standalone SAGE service at `/Users/2madeira/DEV/PROJECTS/SAGE`
and **extract** its document-processing pipeline into `packages/sage` per
`CLAUDE.md` "packages/sage — Document Processing Package". Strip FastAPI, DB,
and HTTP layers. Keep pure pipeline code.

> For every PR in this track: source code lives in the external SAGE repo.
> Copy the relevant module(s), delete imports of FastAPI/SQLAlchemy/persistence,
> rewrite to be a stateless function or small class. Keep the public surface
> minimal — only what `process_document()` needs.

### PR 1.1 — `packages/sage` models

**Files:** `packages/sage/sage/models.py`, `packages/sage/sage/__init__.py`,
`packages/sage/tests/test_models.py`.

**Acceptance:** `Page`, `Chunk`, `ContractFields`, `ExtractedDocument`,
`ProcessingResult` defined as Pydantic models per `CLAUDE.md`. `from sage import
Chunk, ContractFields, ProcessingResult` works.

**Prompt:**
> Define the SAGE Pydantic models exactly as documented in `CLAUDE.md`
> "packages/sage — Key models". `Chunk(text, page_start, page_end, section_type,
> chunk_index, chunk_summary)`. `ContractFields` with all listed Russian
> contract fields, every field `Optional[str]` defaulting to `None`. `Page(index,
> text, kind: Literal["text","scan"])`. `ExtractedDocument(pages, document_kind,
> chunks)`. `ProcessingResult(chunks, fields, summary, pages, document_kind,
> partial)`. Re-export them from `sage/__init__.py`. Unit test: instantiate each
> with all-None fields and serialize via `.model_dump()`.

### PR 1.2 — Conversion (LibreOffice → PDF)

**Files:** `packages/sage/sage/conversion/__init__.py`,
`packages/sage/sage/conversion/libreoffice.py`,
`packages/sage/tests/test_conversion.py` (skip if `soffice` not in PATH).

**Acceptance:** `ensure_pdf(src: Path, work_dir: Path) -> Path` returns the
input unchanged if it's already PDF, otherwise invokes `soffice --headless
--convert-to pdf` and returns the produced PDF path.

**Prompt:**
> Port the LibreOffice conversion logic from the SAGE source repo into
> `packages/sage/sage/conversion/libreoffice.py`. Single async function
> `ensure_pdf(src: Path, work_dir: Path) -> Path`. If `src.suffix.lower() ==
> ".pdf"`, return `src`. Otherwise run `soffice --headless --convert-to pdf
> --outdir <work_dir> <src>` via `asyncio.create_subprocess_exec`, raise
> `ConversionError` on non-zero exit, return the produced PDF path. No
> dependencies on FastAPI or DB.

### PR 1.3 — PDF detection + text extraction

**Files:** `packages/sage/sage/pdf/__init__.py`, `pdf/detector.py`,
`pdf/text_extractor.py`, tests.

**Acceptance:** `detect_kind(pdf_path) -> Literal["text","scan"]` runs the
three-heuristic detector with ЭДО-noise filtering (port from SAGE).
`extract_text_pages(pdf_path) -> list[Page]` returns one `Page` per PDF page
using `pymupdf`.

**Prompt:**
> Port `detect_kind` and `extract_text_pages` from the existing SAGE repo into
> `packages/sage/sage/pdf/`. `detect_kind(pdf_path: Path) -> Literal["text",
> "scan"]` must implement the three-heuristic detector (text length per page,
> ratio of pages with text, ЭДО noise filter) — preserve thresholds from SAGE.
> `extract_text_pages(pdf_path: Path) -> list[Page]` opens with pymupdf and
> returns `Page(index=i, text=page.get_text(), kind="text")`. Unit-test detector
> with a tiny synthesized PDF or by mocking pymupdf.

### PR 1.4 — OCR

**Files:** `packages/sage/sage/pdf/ocr.py`, test (skipped if no tesseract).

**Acceptance:** `ocr_pages(pdf_path) -> list[Page]` rasterizes pages at 300 DPI
and runs `pytesseract` with `lang="rus+eng"`, returning `Page(kind="scan")`.

**Prompt:**
> Port the OCR routine from SAGE into `packages/sage/sage/pdf/ocr.py`. Function
> `ocr_pages(pdf_path: Path) -> list[Page]`: render each page to a 300 DPI PIL
> image via pymupdf, run `pytesseract.image_to_string(img, lang="rus+eng")`,
> return list of `Page(index=i, text=..., kind="scan")`. Use
> `concurrent.futures.ThreadPoolExecutor` to parallelize per-page OCR.

### PR 1.5 — Normalizer

**Files:** `packages/sage/sage/normalizer/__init__.py`,
`packages/sage/sage/normalizer/clean.py`, tests.

**Acceptance:** `normalize_pages(pages) -> list[Page]` strips repeating
headers/footers, collapses whitespace, fixes encoding artifacts, and inserts
canonical page markers. Pure function, fully unit-testable.

**Prompt:**
> Port the text normalization from SAGE into `packages/sage/sage/normalizer/`.
> Single function `normalize_pages(pages: list[Page]) -> list[Page]`. Steps:
> collapse whitespace runs, strip control chars, repair common encoding
> artifacts (mojibake patterns from SAGE), detect and remove repeating
> headers/footers across pages (lines that appear on >60% of pages),
> normalize page break markers. Cover with unit tests using table-driven cases.

### PR 1.6 — Chunker

**Files:** `packages/sage/sage/chunker/__init__.py`,
`packages/sage/sage/chunker/split.py`, tests.

**Acceptance:** `chunk_pages(pages) -> list[Chunk]` splits by pages, then by
markdown-style headings, then with a semantic fallback so each chunk is
≤~2000 chars. Each chunk preserves `page_start`/`page_end`. Pure Python; no LLM.

**Prompt:**
> Port the chunker from SAGE into `packages/sage/sage/chunker/`. Public function
> `chunk_pages(pages: list[Page], max_chars: int = 2000) -> list[Chunk]`.
> Algorithm: (1) start with page-level chunks; (2) within each chunk, split on
> markdown headings (`^#{1,6} `); (3) if any chunk still exceeds `max_chars`,
> apply a semantic fallback (sentence boundary, then paragraph boundary).
> Preserve `page_start`/`page_end` across all splits, set `chunk_index`
> sequentially, set `section_type` from heading level (`"header"` for chunks
> starting with a heading, else `"body"`), `chunk_summary=None` (filled by
> Track 1.7). The chunker MUST NOT call any LLM. Cover edge cases with unit
> tests: empty pages, single huge page, document with no headings, document
> made entirely of headings.

### PR 1.7 — LLM client + extraction & summary prompts

**Files:** `packages/sage/sage/llm/__init__.py`, `llm/client.py`,
`llm/extract.py`, `llm/summary.py`, tests using a mocked client.

**Acceptance:** `LMStudioClient(base_url, model)` exposes async `complete(...)`
and `chat(...)`. `extract_one(client, chunk) -> ContractFields` runs extraction
with one validation retry. `merge_fields(left, right) -> ContractFields`
left-prefers non-null values. `summarize(client, pages) -> str` does map-reduce
(per-page summary, then reduce).

**Prompt:**
> Port LLM logic from SAGE into `packages/sage/sage/llm/`.
> 1. `client.py`: `LMStudioClient(base_url, model)` async wrapper around the
>    OpenAI-compatible chat completions endpoint via `httpx.AsyncClient`. Method
>    `chat(messages, response_format=None) -> str`.
> 2. `extract.py`: prompt template that asks the model to extract every
>    `ContractFields` field from a chunk. The prompt must instruct the model to
>    return strict JSON, never invent values, return `null` for absent fields.
>    `extract_one(client, chunk) -> ContractFields`: call once, parse JSON; on
>    `ValidationError` retry once with the validation error appended; on second
>    failure return `ContractFields()` (all null) and log a warning.
>    `merge_fields(left: ContractFields, right: ContractFields) -> ContractFields`:
>    return new instance where each field is `left.f if left.f is not None else
>    right.f` (left-prefer).
> 3. `summary.py`: `summarize(client, pages) -> str` — map step generates a
>    1–2 sentence summary per page, reduce step consolidates them into a
>    document-level summary (≤500 chars).
> 4. Unit-test `merge_fields` exhaustively (table-driven). Mock the client for
>    `extract_one` retry test. Skip integration tests against a real LM Studio.

### PR 1.8 — `process_document` entry point

**Files:** `packages/sage/sage/process.py`, `packages/sage/sage/__init__.py`
(export `process_document`), tests with mocked sub-steps.

**Acceptance:** `await process_document(src: Path, work_dir: Path) ->
ProcessingResult` orchestrates conversion → detect → extract/OCR → normalize →
chunk → LLM extract per chunk → merge → summarize. Sets
`result.partial=True` if any chunk extraction failed validation twice.

**Prompt:**
> Wire the SAGE pipeline together in `packages/sage/sage/process.py`. Single
> public coroutine: `async def process_document(src: Path, work_dir: Path,
> *, llm_client: LMStudioClient | None = None) -> ProcessingResult`. Steps,
> in order:
> 1. `pdf_path = await ensure_pdf(src, work_dir)`
> 2. `kind = detect_kind(pdf_path)`
> 3. `pages = extract_text_pages(pdf_path) if kind == "text" else ocr_pages(pdf_path)`
> 4. `pages = normalize_pages(pages)`
> 5. `chunks = chunk_pages(pages)`
> 6. for each chunk, call `extract_one(llm_client, chunk)`; reduce via
>    `merge_fields` left-prefer; track `partial = any(extraction returned all-None)`
> 7. `summary = await summarize(llm_client, pages)`
> 8. return `ProcessingResult(chunks, fields, summary, pages, document_kind=kind, partial)`
>
> Re-export `process_document` from `sage/__init__.py`. Default `llm_client` to
> a new `LMStudioClient` from env if not provided. Add a unit test where every
> sub-step is monkeypatched to assert the orchestration order and the
> `ProcessingResult` shape.

---

## Track 2 — Core domain & ports

### PR 2.1 — ID newtypes & base value objects

**Files:** `backend/app/core/domain/ids.py`,
`backend/app/core/domain/__init__.py`, tests.

**Acceptance:** `DocumentId`, `ContractorEntityId`, `ChunkId` defined as
`NewType` over `UUID`. Helpers to generate (`new_*_id()`) and parse from string.

**Prompt:**
> Create `backend/app/core/domain/ids.py`. Define `DocumentId`,
> `ContractorEntityId`, `ChunkId` using `typing.NewType` over `uuid.UUID`. Add
> `new_document_id()`, `new_contractor_entity_id()`, `new_chunk_id()` returning
> `uuid.uuid4()` cast to the newtype. Re-export from
> `core/domain/__init__.py`. Unit-test that the values round-trip through
> `str(...)` and `UUID(...)`.

### PR 2.2 — `UnitOfWork` port

**Files:** `backend/app/core/ports/unit_of_work.py`,
`backend/app/core/ports/__init__.py`.

**Acceptance:** `UnitOfWork` Protocol with async context manager semantics
(`__aenter__`, `__aexit__`, `commit()`, `rollback()`).

**Prompt:**
> Create `backend/app/core/ports/unit_of_work.py` defining a
> `typing.Protocol` `UnitOfWork` with: `async __aenter__`, `async __aexit__`,
> `async commit() -> None`, `async rollback() -> None`. Document the semantic
> contract in a class docstring (≤3 lines): exiting without `commit()` rolls
> back; exceptions inside the block roll back automatically. No implementation
> in this PR.

---

## Track 3 — Persistence baseline

### PR 3.1 — SQLAlchemy session + UoW adapter

**Files:** `backend/app/adapters/sqlalchemy/session.py`,
`backend/app/adapters/sqlalchemy/unit_of_work.py`,
`backend/migrations/` (alembic init), `backend/alembic.ini`.

**Acceptance:** `make_engine(settings)` + `make_sessionmaker(engine)` async.
`SqlAlchemyUnitOfWork` implements the `UnitOfWork` port. `alembic` is wired up
and `alembic current` runs against an empty DB.

**Prompt:**
> Create the SQLAlchemy async baseline in `backend/app/adapters/sqlalchemy/`.
> 1. `session.py`: `make_engine(database_url) -> AsyncEngine`,
>    `make_sessionmaker(engine) -> async_sessionmaker[AsyncSession]`.
> 2. `unit_of_work.py`: `SqlAlchemyUnitOfWork(sessionmaker)` implementing the
>    `UnitOfWork` Protocol from `core/ports`. On `__aenter__` open a session and
>    expose it via `self.session`. `commit()` and `rollback()` proxy to the
>    session. `__aexit__` rolls back on exception then closes.
> 3. Run `alembic init backend/migrations` (async template). Configure
>    `alembic.ini` and `env.py` to read `DATABASE_URL` from env and use the
>    async engine. Leave `target_metadata = None` for now (no models yet).

### PR 3.2 — Initial migration (full schema)

**Files:** `backend/migrations/versions/0001_initial.py`,
`backend/app/adapters/sqlalchemy/models.py` (declarative ORM models matching
the schema).

**Acceptance:** `alembic upgrade head` creates every table in `CLAUDE.md`
"Data Model" with the documented columns, FKs, and constraints.

**Prompt:**
> Create the initial Alembic migration `0001_initial.py` AND the SQLAlchemy
> declarative models in `backend/app/adapters/sqlalchemy/models.py` matching
> `CLAUDE.md` "Data Model" verbatim. Tables: `contractors`,
> `contractor_raw_mappings`, `documents`, `document_chunks`, `extracted_fields`,
> `document_summaries`. Use `UUID(as_uuid=True)`, `JSONB` for
> `extracted_fields.fields`, `ARRAY(Text)` for `document_summaries.key_points`,
> `TIMESTAMP(timezone=True)` for `created_at`. Add `UNIQUE` on
> `contractors.normalized_key`, `extracted_fields.document_id`,
> `document_summaries.document_id`. Set `target_metadata = Base.metadata` in
> `env.py`. Verify locally: `alembic upgrade head` then `alembic downgrade
> base` is clean.

### PR 3.3 — Document repository adapter (CRUD baseline)

**Files:** `backend/app/adapters/sqlalchemy/documents.py`, related ports stub
in `backend/app/features/ingest/ports.py` (just the repo Protocol — full ports
file lands in PR 4.1 but the repo signature is needed here to compile).

**Acceptance:** `SqlAlchemyDocumentRepository` implements `add`, `get`, `list`,
`update_status`, `set_error` for `Document`.

**Prompt:**
> In `backend/app/adapters/sqlalchemy/documents.py` implement
> `SqlAlchemyDocumentRepository` with methods `add(document) -> None`,
> `get(document_id) -> Document`, `list(limit, offset) -> list[Document]`,
> `update_status(document_id, status) -> None`,
> `set_error(document_id, message) -> None`. The `Document` entity import
> resolves to `app.features.ingest.entities.document.Document`. Map between
> ORM rows and the entity by hand (no auto-mapping). Stub
> `app/features/ingest/ports.py` with just the `DocumentRepository` Protocol
> for now (full ports file in PR 4.1).

---

## Track 4 — Ingest feature

### PR 4.1 — Ingest entities & ports

**Files:** `backend/app/features/ingest/entities/document.py`,
`backend/app/features/ingest/ports.py`,
`backend/app/features/ingest/__init__.py`, tests.

**Acceptance:** `Document` aggregate with status transitions
(`mark_processing`, `mark_resolving`, `mark_indexing`, `mark_indexed`,
`mark_failed`). Status enum matches `CLAUDE.md` lifecycle. Ports defined:
`DocumentRepository`, `DocumentFileStorage`, `SageProcessor`,
`ChunkRepository`, `FieldsRepository`, `SummaryRepository`,
`IngestionTaskQueue`.

**Prompt:**
> Create the ingest feature core in `backend/app/features/ingest/`.
> 1. `entities/document.py`: `Document` dataclass with id, contractor_entity_id,
>    title, file_path, content_type, document_kind, doc_type, status,
>    error_message, partial_extraction, created_at. `DocumentStatus` enum:
>    QUEUED, PROCESSING, RESOLVING, INDEXING, INDEXED, FAILED. Methods
>    `mark_processing()`, `mark_resolving()`, `mark_indexing()`,
>    `mark_indexed()`, `mark_failed(message)` — each enforces a valid
>    predecessor state and raises `InvalidStatusTransition` otherwise.
> 2. `ports.py`: Protocols `DocumentRepository`, `ChunkRepository`,
>    `FieldsRepository`, `SummaryRepository`, `DocumentFileStorage`
>    (`save(stream, filename) -> Path`), `SageProcessor` (`process(file_path)
>    -> ProcessingResult`), `IngestionTaskQueue` (`enqueue_process(document_id)
>    -> None`).
> 3. Unit tests for every status transition (allowed and disallowed).

### PR 4.2 — `upload_document` use case

**Files:** `backend/app/features/ingest/use_cases/upload_document.py`, tests.

**Acceptance:** Saves the file via `DocumentFileStorage`, creates `Document`
in QUEUED state, persists, enqueues `process_document` task. Returns
`DocumentId`. Tested with in-memory fakes.

**Prompt:**
> Implement `UploadDocumentUseCase` in
> `backend/app/features/ingest/use_cases/upload_document.py`. Constructor
> deps: `storage: DocumentFileStorage`, `documents: DocumentRepository`,
> `tasks: IngestionTaskQueue`, `uow: UnitOfWork`. `async def execute(self,
> *, file: BinaryIO, filename: str, content_type: str) -> DocumentId`:
> 1. `path = await storage.save(file, filename)`
> 2. build `Document(id=new_document_id(), title=filename, file_path=path,
>    content_type=content_type, status=QUEUED, ...)`
> 3. `async with uow: await documents.add(document); await uow.commit()`
> 4. `await tasks.enqueue_process(document.id)`
> 5. return `document.id`
> Test with in-memory fakes for all four ports; assert add → commit → enqueue
> ordering.

### PR 4.3 — `process_document` use case

**Files:** `backend/app/features/ingest/use_cases/process_document.py`, tests.

**Acceptance:** Loads document, marks PROCESSING, calls `SageProcessor`,
persists chunks, fields, summary, sets `partial_extraction`, commits. On
exception calls `mark_failed` and commits. Does **not** chain the next task —
that lives in the Celery wrapper (Track 9).

**Prompt:**
> Implement `ProcessDocumentUseCase` in
> `backend/app/features/ingest/use_cases/process_document.py`. Constructor
> deps: `documents: DocumentRepository`, `chunks: ChunkRepository`,
> `fields: FieldsRepository`, `summaries: SummaryRepository`,
> `sage: SageProcessor`, `uow: UnitOfWork`.
> `async def execute(self, document_id: DocumentId) -> None`:
> 1. `async with uow:` load document, call `document.mark_processing()`,
>    persist status, commit (so progress is visible immediately).
> 2. `result = await sage.process(document.file_path)` — outside uow.
> 3. `async with uow:` save chunks, fields, summary; set
>    `document.partial_extraction = result.partial` and
>    `document.document_kind = result.document_kind`; commit.
> 4. On any exception in step 2 or 3: open a fresh uow, call
>    `document.mark_failed(str(exc))`, persist, commit, re-raise.
> Tests use in-memory fakes and one fake `SageProcessor` that returns a
> canned `ProcessingResult`. Cover happy path AND exception path.

### PR 4.4 — SAGE adapter + file storage adapter

**Files:** `backend/app/adapters/sage/processor.py`,
`backend/app/adapters/local_fs/file_storage.py` (or
`backend/app/adapters/sqlalchemy/` repos for chunks/fields/summary).

**Acceptance:** `SageProcessorAdapter` implements `SageProcessor` by calling
`sage.process_document(...)`. `LocalFileStorage` implements
`DocumentFileStorage` writing to `settings.upload_dir / <uuid>__<filename>`.
Repositories for chunks/fields/summary.

**Prompt:**
> Wire SAGE and persistence adapters.
> 1. `backend/app/adapters/sage/processor.py`: `SageProcessorAdapter(work_dir,
>    llm_client)` implementing `SageProcessor`. `process(path)` delegates to
>    `sage.process_document(src=path, work_dir=self.work_dir,
>    llm_client=self.llm_client)`.
> 2. `backend/app/adapters/local_fs/file_storage.py`: `LocalFileStorage(base:
>    Path)` implementing `DocumentFileStorage`. `save(stream, filename)`
>    writes to `base / f"{uuid4()}__{filename}"`, ensures parent exists,
>    returns the absolute path.
> 3. `backend/app/adapters/sqlalchemy/`: `SqlAlchemyChunkRepository`,
>    `SqlAlchemyFieldsRepository`, `SqlAlchemySummaryRepository` —
>    straightforward CRUD against the tables created in PR 3.2.
> No business logic. No tests required for adapters per the testing bar.

---

## Track 5 — Contractors feature

### PR 5.1 — Contractor entities, ports, repositories

**Files:** `backend/app/features/contractors/entities/{contractor.py,
resolution.py}`, `features/contractors/ports.py`,
`adapters/sqlalchemy/contractors.py`.

**Acceptance:** `Contractor` aggregate, `RawContractorMapping` value object.
Ports: `ContractorRepository` (incl. `find_by_inn`,
`find_by_normalized_key`, `find_all_for_fuzzy`),
`RawContractorMappingRepository`. SQLAlchemy adapters for both.

**Prompt:**
> Build the contractors feature core. Entities: `Contractor(id, display_name,
> normalized_key, inn, kpp, created_at)`, `RawContractorMapping(id, raw_name,
> inn, contractor_entity_id, confidence)`. Ports: `ContractorRepository` with
> `add`, `get`, `find_by_inn(inn) -> Contractor | None`,
> `find_by_normalized_key(key) -> Contractor | None`,
> `find_all_for_fuzzy() -> list[Contractor]` (returns all rows; fine for MVP),
> `RawContractorMappingRepository` with `add`,
> `find_by_raw(raw_name, inn) -> RawContractorMapping | None`. Implement
> SQLAlchemy adapters in `adapters/sqlalchemy/contractors.py`.

### PR 5.2 — Name normalization + `resolve_contractor`

**Files:** `backend/app/features/contractors/normalization.py`,
`features/contractors/use_cases/resolve_contractor.py`,
`features/contractors/normalization_rules.yaml`, tests.

**Acceptance:** `normalize_name(raw)` strips legal forms, lowercases,
collapses whitespace, applies FIO heuristic. `ResolveContractorUseCase`
implements the 4-step cascade (INN exact → normalized key → fuzzy ≥90 →
create). On success, persists `RawContractorMapping` and updates the document
with the resolved id.

**Prompt:**
> Implement contractor name normalization and resolution.
> 1. `normalization.py`: `normalize_name(raw: str) -> str`. Steps: strip legal
>    form prefixes (ООО, АО, ИП, ПАО, ЗАО, НКО — case-insensitive, surrounded
>    by quotes or whitespace), strip punctuation except spaces, lowercase,
>    collapse whitespace. FIO heuristic: if the result is 2 or 3 Cyrillic
>    tokens, sort them lexicographically and rejoin (canonical FIO form).
>    Load stopwords/legal-form list from `normalization_rules.yaml`.
> 2. `use_cases/resolve_contractor.py`: `ResolveContractorUseCase` with deps
>    `contractors: ContractorRepository`, `mappings:
>    RawContractorMappingRepository`, `documents: DocumentRepository`, `uow:
>    UnitOfWork`. `execute(document_id)`:
>      a. load document, fetch its extracted fields (use a `FieldsRepository`
>         port — add reading method if missing).
>      b. mark RESOLVING.
>      c. cascade per `CLAUDE.md` "Entity Resolution" — INN exact, normalized
>         key, RapidFuzz `token_sort_ratio` ≥ 90 against
>         `find_all_for_fuzzy()`, else create new `Contractor`.
>      d. persist `RawContractorMapping(raw, inn, resolved_id, confidence)`,
>         set `document.contractor_entity_id = resolved_id`, commit.
> 3. Unit-test `normalize_name` thoroughly (table-driven, including FIO cases).
>    Unit-test the cascade with in-memory fakes for each branch.

### PR 5.3 — Profile and listing use cases

**Files:** `features/contractors/use_cases/{get_contractor_profile.py,
list_contractor_documents.py}`, tests.

**Acceptance:** `GetContractorProfileUseCase` returns `Contractor` plus
aggregate counts (documents, mappings). `ListContractorDocumentsUseCase`
returns documents for a contractor, sorted by `created_at desc`, paginated.

**Prompt:**
> Add `GetContractorProfileUseCase` and `ListContractorDocumentsUseCase` in
> `features/contractors/use_cases/`. The profile use case returns a DTO
> `ContractorProfile(contractor, document_count, raw_mapping_count)`. The
> list use case takes `(contractor_entity_id, limit, offset)` and returns
> `list[Document]` sorted by `created_at desc`. Reuse the existing repos —
> add count helpers to `ContractorRepository` and `DocumentRepository` if
> needed (`count_documents_for(id) -> int`, `list_for_contractor(id, limit,
> offset) -> list[Document]`). Test with in-memory fakes.

---

## Track 6 — Indexing

### PR 6.1 — Qdrant adapter + collection bootstrap

**Files:** `backend/app/adapters/qdrant/client.py`,
`backend/app/adapters/qdrant/index.py`,
`backend/app/adapters/qdrant/bootstrap.py`,
`backend/app/features/ingest/ports.py` (extend with `VectorIndex` Protocol).

**Acceptance:** `make_qdrant_client(url)` returns an async client.
`bootstrap_collection(client, name, dim)` is idempotent — creates the
`document_chunks` collection with the configured dim and payload schema if
absent. `QdrantVectorIndex` implements `VectorIndex` (upsert with payload).

**Prompt:**
> Build the Qdrant adapter.
> 1. `client.py`: `make_qdrant_client(url)` returns
>    `qdrant_client.AsyncQdrantClient(url=...)`.
> 2. `bootstrap.py`: `async def bootstrap_collection(client, name: str, dim:
>    int) -> None`. If the collection exists, return. Else create it with a
>    single dense vector of size `dim`, distance `Cosine`, and the payload
>    fields documented in `CLAUDE.md` "Qdrant — Single Collection".
> 3. Extend `features/ingest/ports.py` with `VectorIndex` Protocol:
>    `upsert_chunks(points: list[VectorPoint]) -> None`,
>    `delete_document(document_id) -> None`. Define `VectorPoint(id: UUID,
>    vector: list[float], payload: dict)`.
> 4. `index.py`: `QdrantVectorIndex(client, collection)` implementing
>    `VectorIndex`. Use `qdrant_client.models.PointStruct`. Batch upserts of
>    256 points.

### PR 6.2 — Embedding adapter (LM Studio nomic-embed-text-v1.5)

**Files:** `backend/app/adapters/llm/embeddings.py`,
`backend/app/features/ingest/ports.py` (add `EmbeddingService` Protocol).

**Acceptance:** `LMStudioEmbeddings(base_url, model)` implements
`EmbeddingService.embed(texts) -> list[list[float]]` by calling
`/v1/embeddings`. Batches up to 32 inputs per request, returns 768-dim vectors.

**Prompt:**
> Add the embedding adapter.
> 1. `features/ingest/ports.py`: add `EmbeddingService` Protocol with
>    `async embed(texts: list[str]) -> list[list[float]]`.
> 2. `backend/app/adapters/llm/embeddings.py`: `LMStudioEmbeddings(base_url:
>    str, model: str = "nomic-embed-text-v1.5", batch_size: int = 32)`.
>    `embed(texts)` POSTs to `{base_url}/v1/embeddings` with body
>    `{"model": self.model, "input": batch}` per batch, concatenates the
>    `data[i].embedding` arrays in order. Use `httpx.AsyncClient` with timeout
>    60s. Validate that returned vectors have `settings.embedding_dim`
>    components; raise `EmbeddingDimensionMismatch` otherwise.

### PR 6.3 — `index_document` use case

**Files:** `features/ingest/use_cases/index_document.py`, tests.

**Acceptance:** Loads chunks for the document, embeds them in batches,
upserts to Qdrant with full payload (per `CLAUDE.md`). Also indexes the
document-level summary as a synthetic chunk with `is_summary=True,
chunk_index=-1`. Marks document INDEXED. On failure marks FAILED.

**Prompt:**
> Implement `IndexDocumentUseCase` in
> `features/ingest/use_cases/index_document.py`. Constructor deps:
> `documents: DocumentRepository`, `chunks: ChunkRepository`, `fields:
> FieldsRepository`, `summaries: SummaryRepository`, `embeddings:
> EmbeddingService`, `index: VectorIndex`, `uow: UnitOfWork`.
> `execute(document_id)`:
> 1. mark INDEXING (own uow + commit).
> 2. load document, chunks, fields, summary.
> 3. build `VectorPoint`s for each chunk: payload per `CLAUDE.md` "Qdrant —
>    Single Collection", `is_summary=False`. `id = chunk.id` (UUID).
> 4. add one extra point for the document summary: `chunk_index=-1,
>    is_summary=True, page_start=null, page_end=null`, text = summary text.
> 5. embed all texts in one call (rely on the adapter's batching), zip to
>    points.
> 6. `await index.upsert_chunks(points)`.
> 7. mark INDEXED (own uow + commit).
> 8. exception path: `mark_failed`, commit, re-raise.
> Test with in-memory fakes.

---

## Track 7 — Search feature

### PR 7.1 — `search_contractors` (global topic search)

**Files:** `features/search/ports.py`, `features/search/dto.py`,
`features/search/use_cases/search_contractors.py`,
`adapters/qdrant/search.py`, tests.

**Acceptance:** `SearchContractorsUseCase` embeds the query, runs vector
search (limit ~200, no filter), aggregates hits by `contractor_entity_id`
(prefer Qdrant `group_by` if available), enriches each group with contractor
display name and a top snippet.

**Prompt:**
> Build the global topic search.
> 1. `features/search/ports.py`: `VectorSearch` Protocol with `search(query_
>    vector, limit, filter, group_by=None) -> list[SearchHit | SearchGroup]`.
> 2. `features/search/dto.py`: dataclasses `SearchHit(id, score, payload)`,
>    `SearchGroup(group_key, hits)`,
>    `ContractorSearchResult(contractor_id, name, score, matched_chunks_count,
>    top_snippet)`.
> 3. `adapters/qdrant/search.py`: `QdrantVectorSearch` implementing the port
>    using `client.search` and `client.search_groups`.
> 4. `use_cases/search_contractors.py`: `SearchContractorsUseCase` with deps
>    `embeddings: EmbeddingService`, `vectors: VectorSearch`, `contractors:
>    ContractorRepository`. `execute(query, limit=20)`:
>      a. `[vec] = await embeddings.embed([query])`
>      b. groups = `await vectors.search(vec, limit=200,
>         group_by="contractor_entity_id", group_size=3)`
>      c. for each group: load contractor, build `ContractorSearchResult`
>         with top snippet from highest-scoring hit.
>      d. return top `limit` results.
> Test with a fake `VectorSearch` that returns canned groups.

### PR 7.2 — `search_documents` (within contractor)

**Files:** `features/search/use_cases/search_documents.py`, tests.

**Acceptance:** Filters by `contractor_entity_id`, groups by `document_id`,
returns `[{document_id, title, date, matched_chunks: [{page, snippet}]}]`.

**Prompt:**
> Implement `SearchDocumentsUseCase` in
> `features/search/use_cases/search_documents.py`. Deps: `embeddings`,
> `vectors`, `documents: DocumentRepository`. `execute(contractor_entity_id,
> query, limit=20)`:
> 1. embed query.
> 2. `groups = vectors.search(vec, limit=100, filter=Filter(must=[
>    FieldCondition("contractor_entity_id", MatchValue(contractor_entity_id))
>    ]), group_by="document_id", group_size=3)`
> 3. for each group: load document metadata, return DTO with `matched_chunks
>    = [{page: payload.page_start, snippet: payload.text[:240]}]` for every
>    hit.

### PR 7.3 — `search_within_document`

**Files:** `features/search/use_cases/search_within_document.py`, tests.

**Acceptance:** Filters by `document_id`, returns chunks with score and page
range.

**Prompt:**
> Implement `SearchWithinDocumentUseCase`. Deps: `embeddings`, `vectors`.
> `execute(document_id, query, limit=20)`:
> 1. embed query.
> 2. `hits = vectors.search(vec, limit=limit, filter=Filter(must=[
>    FieldCondition("document_id", MatchValue(document_id))]))`
> 3. return `[{chunk_index, page_start, page_end, section_type, snippet,
>    score}]` mapped from payloads.

---

## Track 8 — Documents feature

### PR 8.1 — Document read use cases

**Files:** `features/documents/use_cases/{get_document.py, list_documents.py,
get_document_facts.py}`, `features/documents/ports.py` (re-export
DocumentRepository or define a thin read port), tests.

**Acceptance:** Three use cases returning DTOs suitable for HTTP responses.
`get_document_facts` returns `{fields, summary, key_points,
partial_extraction}`.

**Prompt:**
> Build read-side use cases for the documents feature.
> 1. `GetDocumentUseCase.execute(document_id) -> DocumentDTO`.
> 2. `ListDocumentsUseCase.execute(limit, offset, status_filter=None,
>    contractor_id_filter=None) -> list[DocumentDTO]`.
> 3. `GetDocumentFactsUseCase.execute(document_id) -> DocumentFactsDTO`
>    combining `extracted_fields` + `document_summaries` rows.
> Define DTOs in `features/documents/dto.py`. Reuse existing repos. Tests
> with in-memory fakes.

---

## Track 9 — Celery & HTTP entrypoints

### PR 9.1 — Celery app

**Files:** `backend/app/celery_app.py`,
`backend/app/adapters/celery/task_queue.py`.

**Acceptance:** Celery app configured per `CLAUDE.md` "Celery Setup".
`CeleryIngestionTaskQueue` implements `IngestionTaskQueue` by enqueueing
the `process_document` Celery task by name.

**Prompt:**
> Create `backend/app/celery_app.py` exactly as in `CLAUDE.md` "Celery Setup":
> broker `redis://redis:6379/0`, backend `redis://redis:6379/1`,
> `task_acks_late=True`, `worker_prefetch_multiplier=1`, JSON serializer.
> Then `backend/app/adapters/celery/task_queue.py`:
> `CeleryIngestionTaskQueue` implementing `IngestionTaskQueue`.
> `enqueue_process(document_id)` uses `celery_app.send_task(
> "ingest.process_document", args=[str(document_id)])` (string task name, not
> import — keeps API container free of worker imports).

### PR 9.2 — Celery tasks (process → resolve → index chain)

**Files:** `backend/app/entrypoints/celery/tasks/ingest.py`,
`backend/app/entrypoints/celery/composition.py` (DI factory functions to
build use cases inside the task process).

**Acceptance:** Three tasks `ingest.process_document`,
`ingest.resolve_contractor`, `ingest.index_document` chained per
`CLAUDE.md` "Celery Setup". Each task constructs its use case via the DI
factory, runs it via `run_async`, then enqueues the next.

**Prompt:**
> Wire the Celery task chain in
> `backend/app/entrypoints/celery/tasks/ingest.py` and a DI factory module
> `entrypoints/celery/composition.py`.
> The factory exposes `build_process_uc()`, `build_resolve_uc()`,
> `build_index_uc()` — each builds the appropriate use case from a freshly
> constructed engine + sessionmaker + adapters using `get_settings()`.
> The tasks:
> ```
> @celery_app.task(bind=True, name="ingest.process_document",
>                  max_retries=3, default_retry_delay=30)
> def process_document(self, document_id: str) -> None:
>     run_async(build_process_uc().execute(DocumentId(UUID(document_id))))
>     resolve_contractor.apply_async(args=[document_id])
> # similar for resolve_contractor (chains index_document) and index_document
> ```
> Implement `run_async(coro)` as `asyncio.new_event_loop().run_until_complete`
> (workers are sync). On any exception inside `execute`, the use case has
> already marked the document FAILED — re-raise so Celery records the failure
> and retries up to `max_retries`.

### PR 9.3 — FastAPI routers (upload, get, list, search, contractors)

**Files:** `backend/app/main.py`,
`backend/app/entrypoints/http/{dependencies.py, documents.py, contractors.py,
search.py}`.

**Acceptance:** `/documents/upload`, `/documents/{id}`, `/documents`,
`/documents/{id}/facts`, `/search`, `/contractors/{id}`,
`/contractors/{id}/documents`, `/contractors/{id}/search`,
`/documents/{id}/search` wired through `Depends()` to use cases. App boots
with `uvicorn app.main:app`.

**Prompt:**
> Build the HTTP entrypoint.
> 1. `entrypoints/http/dependencies.py`: FastAPI `Depends()` factories
>    that build a sessionmaker once at startup and per-request build a uow
>    + repos + use cases. Mirror the Celery composition module so wiring is
>    consistent.
> 2. `entrypoints/http/documents.py`:
>      - `POST /documents/upload` (multipart/form-data, returns 202
>        `{"document_id": ...}`)
>      - `GET /documents/{id}` (DocumentDTO)
>      - `GET /documents` (list, query params `limit, offset, status,
>        contractor_id`)
>      - `GET /documents/{id}/facts` (DocumentFactsDTO)
>      - `GET /documents/{id}/search?q=` (within-document search)
> 3. `entrypoints/http/contractors.py`:
>      - `GET /contractors/{id}`
>      - `GET /contractors/{id}/documents`
>      - `GET /contractors/{id}/search?q=`
> 4. `entrypoints/http/search.py`: `GET /search?q=&limit=`.
> 5. `app/main.py`: build `FastAPI` app, include routers, run
>    `bootstrap_collection` on startup.
> Add CORS allowing `http://localhost:5173` (the frontend dev server) for
> dev.

### PR 9.4 — SSE status stream

**Files:** `backend/app/entrypoints/http/streams.py`, registered in
`main.py`.

**Acceptance:** `GET /documents/{id}/stream` returns
`text/event-stream`, polls document status every ~1s, emits events on
change, closes on INDEXED or FAILED. Works against curl.

**Prompt:**
> Implement the SSE endpoint exactly per `CLAUDE.md` "API Endpoints —
> Ingestion + Progress" → "SSE handler skeleton". File:
> `entrypoints/http/streams.py`, route `GET /documents/{id}/stream` returning
> a `StreamingResponse` of `media_type="text/event-stream"`. Use the
> `_status_stream` async generator from the spec; load the document via the
> existing repository dependency. Manual smoke-test command in the PR
> description: `curl -N
> http://localhost:8000/documents/<uuid>/stream`.

---

## Track 10 — Test frontend (React + Vite, minimal)

Goal: just enough UI to upload a document, watch it move through the
pipeline, browse contractors, and run drill-down search. NOT the MVP
frontend; throwaway-quality.

### PR 10.1 — Vite + React skeleton

**Files:** `frontend/package.json`, `frontend/index.html`,
`frontend/vite.config.ts`, `frontend/tsconfig.json`,
`frontend/src/{main.tsx,App.tsx,api.ts}`, `frontend/src/components/`.

**Acceptance:** `npm install && npm run dev` serves at
`http://localhost:5173` with a placeholder route layout
(`/`, `/contractors/:id`, `/documents/:id`). Calls API via
`VITE_API_URL` (default `http://localhost:8000`).

**Prompt:**
> Scaffold a minimal React + Vite + TypeScript app under `frontend/`. Add
> `react-router-dom` for routing. Create three empty route components:
> `Home` (`/`), `ContractorPage` (`/contractors/:id`), `DocumentPage`
> (`/documents/:id`). Add `frontend/src/api.ts` with a tiny typed `fetch`
> wrapper using `import.meta.env.VITE_API_URL` (default
> `http://localhost:8000`). No styling beyond a single `App.css` with
> minimal layout (flex column, max-width 960px, centered). No state
> library; `useState` is fine for now.

### PR 10.2 — Upload + status

**Files:** `frontend/src/components/{UploadForm.tsx,
DocumentStatus.tsx}`, wired into `Home` and `DocumentPage`.

**Acceptance:** Drag-and-drop or file-input upload posts to
`/documents/upload`. After upload, the UI subscribes to
`/documents/{id}/stream` via `EventSource` and shows live status. On
INDEXED, link to the document page.

**Prompt:**
> Add an upload form on `Home` posting multipart to `/documents/upload`. On
> 202, redirect to `/documents/{id}`. On `DocumentPage`, show document
> metadata (`GET /documents/{id}`) and open an `EventSource` against
> `/documents/{id}/stream`. Render the status as a stepper:
> QUEUED → PROCESSING → RESOLVING → INDEXING → INDEXED. On FAILED show the
> error message. Close the EventSource on terminal state. Once INDEXED,
> show the extracted fields and summary (`GET /documents/{id}/facts`).

### PR 10.3 — Search drill-down

**Files:** `frontend/src/components/{SearchBar.tsx,
ContractorSearchResults.tsx, DocumentResults.tsx, ChunkResults.tsx}`,
wired into `Home`, `ContractorPage`, `DocumentPage`.

**Acceptance:** On `/`, search bar hits `/search?q=...`, lists contractors
with snippets; click → contractor page. On `/contractors/:id`, shows
`/contractors/:id/documents` and a search bar hitting
`/contractors/:id/search`; click → document page. On `/documents/:id`,
search bar hits `/documents/:id/search`, shows chunk-level results with
page numbers and snippets.

**Prompt:**
> Build the drill-down search UI:
> - `Home`: contractor-level search results from `GET /search?q=`. Each
>   result links to `/contractors/{id}`.
> - `ContractorPage`: shows the contractor profile (`GET /contractors/{id}`),
>   document list (`GET /contractors/{id}/documents`), and a search bar
>   hitting `GET /contractors/{id}/search?q=`. Document results link to
>   `/documents/{id}`.
> - `DocumentPage` (extends PR 10.2): adds a search bar hitting
>   `GET /documents/{id}/search?q=`, rendering chunk-level matches
>   (page range, section_type, snippet, score).
> Snippets are highlighted on the query terms (simple substring split, no
> highlighter library needed). No pagination; just `limit=20` in queries.

---

## End of MVP

After PR 10.3 merges, ARGUS supports the full `CLAUDE.md` happy path:
upload → SAGE pipeline → field extraction → entity resolution → indexing →
drill-down semantic search across contractors, documents, and document
fragments — with a minimal UI to exercise it end-to-end.

---

## Post-MVP (deferred — not part of this roadmap's PRs)

To be planned separately once the MVP is stable. Listed here so they aren't
silently forgotten.

- **Auth.** JWT, `owner_id` on `Document` and `Contractor`, row-level
  filtering through every repository.
- **Multi-tenancy.** Workspace scoping on every aggregate; Qdrant payload
  filter by `workspace_id`.
- **Observability.** Structured logging (JSON), OpenTelemetry traces across
  HTTP → Celery → SAGE, dashboards for queue depth + per-stage latency,
  Sentry for unhandled exceptions.
- **CI/CD.** GitHub Actions: lint (ruff), typecheck (mypy),
  unit tests on push; build + push images on `main`; preview environments
  per PR.
- **Adapter integration tests.** testcontainers for Postgres + Qdrant +
  Redis; end-to-end ingestion test running real SAGE.
- **Production frontend.** Replace the Track 10 throwaway with the real
  ARGUS web app — design system, accessibility pass, auth flows, full
  drill-down UX.
- **Hardening.** File-type validation on upload, antivirus scan, size
  limits, rate limiting, idempotent uploads, retry/backoff policies for
  LM Studio outages, dead-letter queue for repeatedly-failing documents.
- **Operations.** Backups for Postgres + Qdrant snapshots, replay tooling
  for re-indexing all documents, schema migrations runbook.
