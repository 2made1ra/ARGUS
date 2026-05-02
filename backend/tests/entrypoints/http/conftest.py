"""Shared fixtures for HTTP entrypoint smoke tests."""
from __future__ import annotations

import pytest
from fastapi import FastAPI

from app.main import app as _app


@pytest.fixture()
def app() -> FastAPI:
    """Return the app instance with a clean dependency_overrides slate."""
    _app.dependency_overrides.clear()
    yield _app
    _app.dependency_overrides.clear()
