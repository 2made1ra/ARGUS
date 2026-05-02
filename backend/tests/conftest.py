"""Root test configuration.

Sets required environment variables at module load time — before any app
module is imported by sub-conftest files or tests.
"""
from __future__ import annotations

import os

# Must be set before any app module that calls get_settings() at import time
# (celery_app.py triggers this via CeleryIngestionTaskQueue import chain).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("LM_STUDIO_URL", "http://localhost:1234/v1")
os.environ.setdefault("LM_STUDIO_LLM_MODEL", "test-model")
