# ARGUS
This file is loaded automatically by Claude Code and must stay concise and universally applicable to all tasks.

ARGUS is moving to a catalog-first MVP for event agency managers. The primary
MVP flow is:

`prices.csv -> price_items -> price_items_search_v1 -> unified assistant chat`

Postgres `price_items` is the source of truth for catalog facts. Qdrant
`price_items_search_v1` is the controlled vector index for catalog search.
Existing PDF/document intelligence remains available as a secondary workflow:
users can upload contracts, extract structured fields, resolve contractors,
index document chunks in Qdrant, and use drill-down document search/RAG.

Do not make changes until you are 95 percent sure of the task. Ask questions until then.

---

## Repository state

The project is **fully implemented** and running. Backend, frontend, and the
`packages/sage` document processing package all exist with tests.
Inspect the actual file tree before any task — never assume something is missing
or planned.

---

## Architecture

Vertical slice + hexagonal core. Three layers:

```
features/   End-to-end workflows (ingest, contractors, search, documents)
core/       Shared domain types and abstract ports (Protocols)
adapters/   External dependency implementations (Postgres, Qdrant, Celery, LLM)
```

See [docs/agent/architecture.md](docs/agent/architecture.md) for the full repo layout and layer rules.

---

## Tech stack

- Python 3.13+ (`requires-python = ">=3.13"`)
- FastAPI + uvicorn
- Celery + Redis
- SQLAlchemy 2.x async + Alembic (3 migrations applied)
- Pydantic v2 + pydantic-settings
- PostgreSQL
- Qdrant
- `packages/sage` — standalone document processing (uv workspace member)
- LM Studio via OpenAI-compatible API
- React 18 + Vite + TypeScript (`frontend/`)
- `ruff` and `pytest` — configured at workspace root

---

## Non-negotiable rule

**Domain and business logic must live in application/domain services — never in entrypoints or adapters.**

- FastAPI routes, Celery tasks, CLI scripts: orchestrate only; no product decisions.
- Adapters implement interfaces; they do not own logic.
- Features communicate through explicit service contracts, not cross-imports.
- The ingestion pipeline must stay modular: conversion → extraction/OCR → normalization → chunking → LLM extraction → persistence → embeddings/indexing.

Catalog MVP rules:

- `prices.csv` populates `price_items`; PDF-to-catalog extraction is post-MVP.
- New catalog embeddings come from deterministic `embedding_text` (`prices_v1`).
- CSV legacy `embedding` is audit-only and must not be used for user query search.
- Assistant responses keep `message`, `router`, `brief`, and `found_items` separate.
- Catalog search returns checkable Postgres item cards/table, not RAG prose.
- Document chunks and catalog rows must use separate Qdrant collections.

---

## Drift guards

Things Claude tends to get wrong — don't do these:

1. **Over-expanding agent files.** Keep root CLAUDE.md short. Heavy reference goes in `docs/agent/`.
2. **Treating docs as accurate without inspecting the repo first.** Always verify against the actual file tree.
3. **Putting business logic in routes, workers, or adapters.** It belongs in services.
4. **Large mixed-purpose PRs.** Separate scaffolding, refactoring, features, and infra changes.
5. **Inventing commands, schemas, or config that aren't in the repo.** Check first; if missing, say so.
6. **Writing style rules here.** Use `ruff` and `pytest` for formatting, linting, and tests. Do not add style rules to `CLAUDE.md`.

---

## Commands

```bash
# Infrastructure (Postgres, Redis, Qdrant)
make infra-up / make infra-down

# Local development
make dev          # FastAPI hot reload on :8000
make worker       # Celery worker
make migrate      # Alembic upgrade head

# Full Docker stack (API + worker containers)
make app-up / make app-down

# Tests and linting (run from repo root)
pytest
ruff check .
ruff format .
```

See [docs/agent/dev.md](docs/agent/dev.md) for environment setup and full workflow.
---

## Workflow conventions

**PRs** — small and single-purpose. Do not mix scaffolding, refactoring, feature work,
and infrastructure in one PR unless explicitly asked.

**Planning** — for non-trivial changes, produce an implementation plan first: affected files,
migration risks, tests, rollback considerations. Wait for approval before coding.

**Behavior preservation** — preparatory refactors must not change behavior. Call out any
behavior change explicitly.

**Commit messages** — Conventional Commits:
`<type>(<scope>): <short imperative summary>`
Add a bullet-point body for non-trivial commits.

**Branch naming** — `feat/*`, `fix/*`, `refactor/*`, `docs/*`, `chore/*`

---

## Reference docs

Read only the docs relevant to the current task (do not load all by default):

- Architecture / repo layout / layer boundaries → [docs/agent/architecture.md](docs/agent/architecture.md)
- Postgres schema / Qdrant payload / extracted fields → [docs/agent/data-model.md](docs/agent/data-model.md)
- Upload, processing, Celery chain, document status → [docs/agent/pipeline.md](docs/agent/pipeline.md)
- Catalog search, assistant chat, document search, Qdrant filters → [docs/agent/search.md](docs/agent/search.md)
- Contractor matching, INN, fuzzy matching, normalization → [docs/agent/entity-resolution.md](docs/agent/entity-resolution.md)
- Dev setup, Makefile, env vars, Docker services → [docs/agent/dev.md](docs/agent/dev.md)
