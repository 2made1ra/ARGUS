# API Contract

`openapi.yaml` is a checked-in snapshot of the FastAPI contract for ARGUS.

The runtime source of truth is still `backend/app/main.py` and the routers under
`backend/app/entrypoints/http/`. When endpoint signatures or response models
change, regenerate the snapshot from the application:

```bash
PYTHONPATH=backend:packages/sage .venv/bin/python -c 'from pathlib import Path; import yaml; from app.main import app; Path("docs/api/openapi.yaml").write_text(yaml.safe_dump(app.openapi(), allow_unicode=True, sort_keys=False), encoding="utf-8")'
```

During local development, FastAPI also serves the live interactive docs at
`/docs` and the live OpenAPI document at `/openapi.json`.
