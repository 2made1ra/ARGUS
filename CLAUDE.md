@AGENTS.md

# ARGUS Claude Code Notes

Claude Code loads this file automatically. Shared repository instructions live
in `AGENTS.md`; this file intentionally imports them and keeps only
Claude-specific reminders so memory stays compact.

## Current Product Direction

ARGUS is a catalog-first event-agency tool. The primary backend data path is:

```text
prices.csv -> price_items -> price_items_search_v1 -> assistant chat
```

The assistant UX is now two-mode:

- `brief_workspace` for explicit event creation, planning, preparation or brief
  rendering.
- `chat_search` for direct contractor, supplier, item, service or price search.

Read `docs/agent/assistant.md` before changing assistant orchestration, router
DTOs, frontend assistant UX, supplier verification, event brief rendering or
candidate selection behavior.

## Claude Memory Rules

- Keep root memory short and operational; put detailed task instructions in
  `docs/agent/`.
- Prefer importing shared instructions with `@AGENTS.md` instead of duplicating
  them here.
- Do not turn `CLAUDE.md` into a plan archive. Catalog-first plans live under
  `docs/plans/catalog-first-refactor/`.
- If repository facts conflict with older docs, inspect the code and update the
  task-specific `docs/agent/` file rather than expanding this file.

## Reference Docs

Read only the task-specific reference after `AGENTS.md`:

- Assistant workflow, UX modes, tools, evidence rules:
  `docs/agent/assistant.md`.
- Architecture / repo layout / layer boundaries:
  `docs/agent/architecture.md`.
- Postgres schema / Qdrant payload / extracted fields:
  `docs/agent/data-model.md`.
- Catalog search, document search/RAG, Qdrant filters:
  `docs/agent/search.md`.
- Upload, processing, Celery chain, document status:
  `docs/agent/pipeline.md`.
- Contractor matching and supplier verification boundary:
  `docs/agent/entity-resolution.md`.
- Dev setup, Makefile, env vars, Docker services:
  `docs/agent/dev.md`.
- HTTP contracts:
  `docs/api/openapi.yaml`.
