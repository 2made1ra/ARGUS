from pathlib import Path

import pytest
from app.config import Settings, get_settings
from pydantic import ValidationError

CONFIG_ENV_KEYS = (
    "DATABASE_URL",
    "REDIS_URL",
    "QDRANT_URL",
    "LM_STUDIO_URL",
    "LM_STUDIO_EMBEDDING_MODEL",
    "LM_STUDIO_LLM_MODEL",
    "UPLOAD_DIR",
    "QDRANT_COLLECTION",
    "EMBEDDING_DIM",
)
ENV_KEYS = CONFIG_ENV_KEYS + tuple(key.lower() for key in CONFIG_ENV_KEYS)


def set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://argus:argus@localhost:5432/argus",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("LM_STUDIO_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("LM_STUDIO_LLM_MODEL", "local-llm")


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch: pytest.MonkeyPatch):
    get_settings.cache_clear()
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    yield

    get_settings.cache_clear()


def test_settings_parses_env_and_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.database_url == (
        "postgresql+asyncpg://argus:argus@localhost:5432/argus"
    )
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.lm_studio_url == "http://localhost:1234/v1"
    assert settings.lm_studio_llm_model == "local-llm"
    assert settings.lm_studio_embedding_model == "nomic-embed-text-v1.5"
    assert settings.upload_dir == Path("/data/uploads")
    assert settings.qdrant_collection == "document_chunks"
    assert settings.embedding_dim == 768


def test_settings_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required_env(monkeypatch)
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert any(error["loc"] == ("database_url",) for error in exc_info.value.errors())


def test_settings_requires_lm_studio_url(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required_env(monkeypatch)
    monkeypatch.delenv("LM_STUDIO_URL")

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert any(error["loc"] == ("lm_studio_url",) for error in exc_info.value.errors())


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required_env(monkeypatch)

    first = get_settings()
    second = get_settings()

    assert first is second
