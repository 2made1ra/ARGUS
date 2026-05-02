# ARGUS
This file is loaded automatically by Claude Code and must stay concise and universally applicable to all tasks.

Document intelligence platform for contractor management and contract search.
Users upload contracts; the system extracts structured fields, resolves contractor
entities, indexes chunks in Qdrant, and exposes a drill-down semantic search UX.

Do not make changes until you are 95 percent sure of the task. Ask questions until then.

---

## Repository state

This project is **greenfield**. The root contains planning and documentation files;
the backend scaffold may not exist yet. Before any implementation work:

1. Inspect the actual repository tree.
2. Clearly distinguish existing files from planned architecture.
3. If something is missing, say so and propose the smallest next step.

Never treat planned architecture as existing code.

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

Planned stack, do not assume configured files exist yet:

- Python 3.13+
- FastAPI + uvicorn
- Celery + Redis
- SQLAlchemy 2.x async + Alembic
- Pydantic-V2
- PostgreSQL
- Qdrant
- `packages/sage` for document processing
- LM Studio via OpenAI-compatible API
- `ruff` and `pytest` once configured

---

## Non-negotiable rule

**Domain and business logic must live in application/domain services — never in entrypoints or adapters.**

- FastAPI routes, Celery tasks, CLI scripts: orchestrate only; no product decisions.
- Adapters implement interfaces; they do not own logic.
- Features communicate through explicit service contracts, not cross-imports.
- The ingestion pipeline must stay modular: conversion → extraction/OCR → normalization → chunking → LLM extraction → persistence → embeddings/indexing.

---

## Drift guards

Things Claude tends to get wrong — don't do these:

1. **Over-expanding agent files.** Keep root CLAUDE.md short. Heavy reference goes in `docs/agent/`.
2. **Treating planned architecture as existing code.** Always inspect the repo first.
3. **Putting business logic in routes, workers, or adapters.** It belongs in services.
4. **Large mixed-purpose PRs.** Separate scaffolding, refactoring, features, and infra changes.
5. **Inventing commands, schemas, or config that aren't in the repo.** Check first; if missing, say so.
6. **Writing style rules here.** Use planned deterministic tools (`ruff`, `pytest`) for formatting, linting, and tests once configured. Do not add long style rules to `CLAUDE.md`.

---

## Commands

Configured commands: none yet.

Planned baseline, only after the corresponding files exist:

```bash
ruff check .
ruff format .
pytest
uvicorn app.main:app --reload
docker compose up -d
```
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

For each task, read root `CLAUDE.md` first, then read only the specific reference docs needed for that task.
Do not load all docs by default.

Read only the docs relevant to the current task:

- Architecture / repo layout / layer boundaries → [docs/agent/architecture.md](docs/agent/architecture.md)
- Postgres schema / Qdrant payload / extracted fields → [docs/agent/data-model.md](docs/agent/data-model.md)
- Upload, processing, Celery chain, document status → [docs/agent/pipeline.md](docs/agent/pipeline.md)
- Semantic search, drill-down UX, Qdrant filters → [docs/agent/search.md](docs/agent/search.md)
- Contractor matching, INN, fuzzy matching, normalization → [docs/agent/entity-resolution.md](docs/agent/entity-resolution.md)
