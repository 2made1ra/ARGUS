# ARGUS Agent Instructions

These instructions apply to the whole repository. If a nested `AGENTS.md` is
added later, the more specific file wins for files under that directory.

## Project Snapshot

ARGUS is a document intelligence platform for contractor management and contract
search. The intended user flow is:

`topic search -> contractor profile -> contractor documents -> search inside a document`

At the moment this repository is still in the planning/foundation stage:

- `CLAUDE.md` is the main architecture brief.
- `docs/architecture/ARCHITECTURE_ROADMAP.md` and
  `docs/architecture/roadmap/*.md` describe implementation tracks.
- `README.md` is only a placeholder.
- The planned `backend/`, `packages/sage/`, `docker-compose.yml`, and Python
  package manifests may not exist yet. Do not invent commands or files as if
  they already exist.

## Source Of Truth

Read these before making architectural or broad implementation changes:

1. `CLAUDE.md`
2. `docs/architecture/ARCHITECTURE_ROADMAP.md`
3. The relevant file in `docs/architecture/roadmap/`

If these sources conflict, prefer `CLAUDE.md` for repository layout and core
architecture, then mention the conflict in your final response.

## Architecture Rules

ARGUS uses vertical slices around a hexagonal core:

- `features/` owns end-to-end workflows.
- `core/` contains shared domain types and shared abstract ports.
- `adapters/` contains external integrations such as Postgres, Qdrant, Celery,
  SAGE, and LLM clients.

Follow these rules:

- Features must not import from each other.
- Shared types used by multiple features belong in `core/domain/`.
- Feature-specific ports are defined inside that feature.
- Adapters implement ports and live under `adapters/`.
- Use cases receive dependencies through constructor injection.
- Do not add global state or a DI framework.
- HTTP handlers and Celery tasks stay thin: call use cases, map errors, and
  handle transport concerns only.
- Do not add a domain event bus. The ingestion pipeline uses explicit Celery
  task chaining.

## Planned Repository Layout

The target structure is:

```text
backend/
  app/
    core/
    features/
      ingest/
      contractors/
      search/
      documents/
    adapters/
    entrypoints/
  migrations/
  tests/
packages/
  sage/
docs/
docker-compose.yml
```

Keep new files within this shape unless the roadmap explicitly says otherwise.

## SAGE Package Rules

`packages/sage` is the standalone document processing package. It must remain
stateless and side-effect-free:

- Input: a source file path plus a work directory.
- Output: a structured `ProcessingResult`.
- No database access.
- No HTTP server.
- No Celery dependency.
- The LLM never creates chunks; chunking is pure Python.
- Extracted contract fields must not be invented. Use `None`/`null` when a value
  is not found.

## Ingestion Pipeline Rules

The document lifecycle is:

`QUEUED -> PROCESSING -> RESOLVING -> INDEXING -> INDEXED`

Any stage may move to `FAILED` and must persist an error message.

The pipeline stages are:

1. Upload stores the file, creates a `Document(status=QUEUED)`, and enqueues
   `process_document`.
2. `process_document` calls SAGE, stores chunks, fields, summaries, and partial
   extraction state.
3. `resolve_contractor` resolves the supplier using INN, normalized name, fuzzy
   match, or creates a new contractor.
4. `index_document` embeds chunks and summary content into Qdrant.

Do not replace this with hidden orchestration, background side effects, or
cross-feature calls.

## Development Commands

Current repository state: no runnable Python or Docker project is present yet.
Use file/documentation checks only until Track 0 creates the monorepo skeleton.

When the relevant files exist, use the commands specified by the roadmap:

```bash
pip install -e backend
pip install -e packages/sage
python -c "import sage; from app import core, features, adapters, entrypoints"
pytest backend/tests/test_config.py -v
docker compose config -q
docker compose up -d postgres redis qdrant
```

Before adding or changing commands in this file, verify them against the actual
manifests in the repository.

## Testing Guidance

- Add or update tests for any behavior change.
- Prefer focused tests for the feature/use case being changed.
- Use broader integration tests when touching adapters, persistence, task
  chaining, or API entrypoints.
- Do not require Postgres, Redis, Qdrant, LibreOffice, Tesseract, or LM Studio
  for unit tests unless the test is explicitly an integration/system test.
- If a test command cannot run because the project skeleton is not present yet,
  say that clearly in the final response.

## Dependency And Infrastructure Rules

- Python target: 3.13+.
- API: FastAPI and uvicorn.
- Tasks: Celery with Redis.
- Persistence: SQLAlchemy 2.x async and Alembic.
- Data validation / DTOs: Pydantic v2 (no Pydantic v1).
- Vector search: Qdrant.
- LLM and embeddings: LM Studio via an OpenAI-compatible API.
- Do not add new infrastructure such as nginx, Traefik, Prometheus, or a CI
  system unless the roadmap or user explicitly asks for it.
- Do not commit secrets. Keep real credentials out of `.env`, `.env.example`,
  docs, tests, and generated examples.
- Always add type annotations to all function parameters and return values; internal
  variables may omit annotations when the type is unambiguous from the right-hand side.
  Run `mypy --strict` to verify.

## When To Ask Before Proceeding

Do not make changes unless you are highly confident about the task. Ask clarifying questions when requirements are ambiguous.

Ask the user before:

- Choosing between conflicting architecture instructions that affect code shape.
- Adding dependencies not named in the relevant roadmap track.
- Changing the ingestion lifecycle, task chaining, or document status model.
- Introducing a new external service or persistent storage.
- Creating broad implementation work outside the requested track.

For small local implementation details, follow the existing architecture and keep
the change narrow.
