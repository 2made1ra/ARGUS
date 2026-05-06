# ARGUS Agent Instructions

These instructions apply to the whole repository. If a nested `AGENTS.md` is
added later, the closest file to the edited path wins; explicit user prompts
override repository instructions.

Keep this file concise and operational. Put detailed reference in `docs/agent/`
and link to it here instead of copying it.

## Project Snapshot

ARGUS is a document intelligence platform for contractor management and contract
search. Core flow:

`topic search -> contractor profile -> contractor documents -> search inside a document`

The repo is an implemented monorepo with `backend/`, `frontend/`,
`packages/sage/`, Docker infrastructure, and tests. Inspect the actual file tree
before each task; do not assume a component is missing or only planned. Do not
make code changes until you are at least 95 percent sure of the task; ask if the
requirement is ambiguous.

## Source Of Truth

For broad architecture, pipeline, data model, API, or workflow changes, read
`CLAUDE.md` first, then only the task-specific reference:

- Architecture and layer rules: `docs/agent/architecture.md`.
- Dev setup, commands, env vars, Docker services: `docs/agent/dev.md`.
- Upload, SAGE processing, Celery chain, statuses: `docs/agent/pipeline.md`.
- Postgres tables, Qdrant payloads, extracted fields: `docs/agent/data-model.md`.
- Search UX, RAG endpoints, Qdrant filters: `docs/agent/search.md`.
- Contractor matching and normalization: `docs/agent/entity-resolution.md`.
- HTTP request/response contracts: `docs/api/openapi.yaml`.

If sources conflict, prefer `CLAUDE.md` for repository-level architecture and
rules, then mention the conflict in the final response. Files under
`docs/archive/` are historical context, not current implementation instructions.

## Repository Shape

Top-level shape: `backend/app/{core,features,adapters,entrypoints}/`,
`backend/{migrations,tests}/`, `packages/sage/`, `frontend/`,
`docs/{agent,api/openapi.yaml}`, `docker-compose.yml`, and `Makefile`. Keep new
files inside this shape unless the relevant `docs/agent/` guide or the user
explicitly asks for another location.

## Architecture Rules

ARGUS uses vertical slices around a hexagonal core. `features/` owns workflows,
entities, use cases, and feature ports; `core/` owns shared domain types and
shared abstract ports; `adapters/` owns external integrations; `entrypoints/`
owns FastAPI routers and Celery tasks.

- Business logic belongs in application/domain services, never in entrypoints or
  adapters.
- Features must not import from each other. Use explicit contracts and shared
  core types.
- Feature-specific ports live inside the feature; implementations live in
  `adapters/`.
- Use cases receive dependencies through constructor injection.
- Do not add global state, a DI framework, cross-feature calls, or a domain
  event bus.
- HTTP handlers, Celery tasks, and CLI scripts stay thin: call use cases, map
  errors, and handle transport concerns.
- Preparatory refactors must preserve behavior unless the user asks otherwise.

## SAGE And Pipeline

`packages/sage` is standalone, stateless, and side-effect-free:

- Input: source file path plus work directory.
- Output: `ProcessingResult`; public entry point:
  `from sage import process_document, ProcessingResult`.
- No database, HTTP server, or Celery dependency.
- LLM output never creates chunks; chunking is pure Python.
- Extracted contract fields must not be invented. Use `None`/`null` when absent.

Document lifecycle:

`QUEUED -> PROCESSING -> RESOLVING -> INDEXING -> INDEXED`

Any stage may move to `FAILED` and must persist an error message.
`document.status` is the source of truth for polling and SSE. Keep the explicit
task chain: upload stores file and enqueues `process_document`; processing
stores chunks, fields, summaries, and partial extraction state;
`resolve_contractor` links or creates the contractor; `index_document` embeds
chunks and document-level summaries into Qdrant. Do not change this lifecycle,
task chaining, or Qdrant payload contract without user approval.

## Commands

Run from the repo root unless noted. Verify commands against `Makefile`,
`pyproject.toml`, `backend/pyproject.toml`, `packages/sage/pyproject.toml`, and
`frontend/package.json` before editing this section.

```bash
uv sync

make infra-up
make infra-down
make infra-logs
make infra-ps

make dev
make worker
make migrate

make app-up
make app-down

pytest
pytest backend/tests/features/test_search.py
ruff check .
ruff check . --fix
ruff format .

cd frontend
npm install
npm run dev
npm run build
```

Prefer focused checks for changed files, then broaden when touching shared
contracts, persistence, task chaining, API schemas, or frontend build contracts.

## Testing And Verification

- Add or update tests for behavior changes.
- Unit tests must not require Postgres, Redis, Qdrant, LibreOffice, Tesseract,
  or LM Studio unless explicitly marked as integration/system tests.
- Frontend changes must preserve the drill-down UX and use
  `docs/api/openapi.yaml` plus `frontend/src/api.ts` as API references.
- If relevant verification cannot run because infrastructure or local tools are
  unavailable, say that clearly in the final response.

## Dependencies And Scope

Tech stack: Python 3.13+, FastAPI, uvicorn, Celery, Redis, SQLAlchemy 2.x async,
Alembic, Pydantic v2, pydantic-settings, PostgreSQL, Qdrant, `packages/sage`,
LM Studio via an OpenAI-compatible API, React 18, Vite, TypeScript, and `ruff`.
Add type annotations to all function parameters and return values. Do not commit
secrets or put real credentials in `.env`, `.env.example`, docs, tests, logs, or
generated examples.

Ask before adding dependencies or external services, introducing new
infrastructure, changing deployment/CI behavior, deleting files, running
destructive commands, or starting broad work outside the requested feature or
layer.

## Git And Maintenance

Keep PRs small and single-purpose; do not mix scaffolding, refactoring, feature
work, and infrastructure unless asked. Branch names should use `feat/*`,
`fix/*`, `refactor/*`, `docs/*`, or `chore/*`. Commit messages use Conventional
Commits: `<type>(<scope>): <short imperative summary>`. Do not commit, push, or
open a PR unless the user asks for it. Treat `AGENTS.md` as living
documentation: keep commands concrete, update it when repo structure or workflow
expectations change, and add nested `AGENTS.md` files for subproject-specific
rules instead of expanding root guidance indefinitely.
