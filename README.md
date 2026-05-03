# ARGUS

Document intelligence platform for contractor management and contract search.

## Quick start

See [CLAUDE.md](CLAUDE.md) for architecture overview and development conventions.

See [ARCHITECTURE_ROADMAP.md](docs/architecture/ARCHITECTURE_ROADMAP.md) for the implementation roadmap.

See [OpenAPI contract](docs/api/openapi.yaml) for the current HTTP API snapshot.

## Packages

| Package | Path | Purpose |
|---------|------|---------|
| `argus-backend` | `backend/` | FastAPI app, Celery workers, domain logic |
| `sage` | `packages/sage/` | Stateless document processing (PDF, OCR, chunking) |

## Install (development)

```bash
uv sync
```

Runs `uv sync` from the repo root — installs both workspace members (`backend` and `packages/sage`) into a shared `.venv`.

## Checks

```bash
uv run --group dev ruff check .
uv run --group dev ruff format .
uv run --project backend pytest backend/tests/test_config.py -v
```
