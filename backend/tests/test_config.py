from collections.abc import Generator
from pathlib import Path

import pytest
from app.config import REPO_ROOT, Settings, get_settings
from pydantic import ValidationError

CONFIG_ENV_KEYS = (
    "DATABASE_URL",
    "REDIS_URL",
    "QDRANT_URL",
    "LLM_BASE_URL",
    "API_KEY",
    "EMBEDDING_MODEL",
    "CHAT_MODEL",
    "LM_STUDIO_URL",
    "LM_STUDIO_EMBEDDING_MODEL",
    "LM_STUDIO_LLM_MODEL",
    "UPLOAD_DIR",
    "DOCUMENT_QDRANT_COLLECTION",
    "DOCUMENT_EMBEDDING_DIM",
    "CATALOG_QDRANT_COLLECTION",
    "CATALOG_EMBEDDING_MODEL",
    "CATALOG_EMBEDDING_DIM",
    "CATALOG_EMBEDDING_TEMPLATE_VERSION",
    "CATALOG_DOCUMENT_PREFIX",
    "CATALOG_QUERY_PREFIX",
    "ASSISTANT_AGENT_MAX_TOOL_CALLS_PER_TURN",
    "ASSISTANT_AGENT_MAX_ITERATIONS",
    "ASSISTANT_AGENT_TIMEOUT_SECONDS",
    "RAG_ANSWER_TIMEOUT_SECONDS",
    "ARGUS_DEMO_MODE",
    "ARGUS_DEMO_CATALOG_CSV_PATH",
)
ENV_KEYS = CONFIG_ENV_KEYS + tuple(key.lower() for key in CONFIG_ENV_KEYS)
ENV_FILE_KEYS = ENV_KEYS + ("ALEMBIC_DATABASE_URL", "alembic_database_url")


def set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://argus:argus@localhost:5432/argus",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.vsellm.ru/v1")
    monkeypatch.setenv("CHAT_MODEL", "openai/gpt-oss-120b")


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    get_settings.cache_clear()
    for key in ENV_FILE_KEYS:
        monkeypatch.delenv(key, raising=False)

    yield

    get_settings.cache_clear()


def _settings_without_env_file() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]  # pydantic-settings runtime option
    )


def test_settings_parses_env_and_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required_env(monkeypatch)

    settings = _settings_without_env_file()

    assert settings.database_url == (
        "postgresql+asyncpg://argus:argus@localhost:5432/argus"
    )
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.llm_base_url == "https://api.vsellm.ru/v1"
    assert settings.api_key is None
    assert settings.embedding_model == "openai/text-embedding-3-small"
    assert settings.chat_model == "openai/gpt-oss-120b"
    assert settings.lm_studio_url == "https://api.vsellm.ru/v1"
    assert settings.lm_studio_llm_model == "openai/gpt-oss-120b"
    assert settings.lm_studio_embedding_model == "openai/text-embedding-3-small"
    assert settings.upload_dir == Path("/data/uploads")
    assert settings.document_qdrant_collection == "document_chunks"
    assert settings.document_embedding_dim == 768
    assert settings.catalog_qdrant_collection == "price_items_search_v1"
    assert settings.catalog_embedding_model == "text-embedding-3-small"
    assert settings.catalog_embedding_dim == 1536
    assert settings.catalog_embedding_template_version == "legacy_csv_embedding"
    assert settings.catalog_document_prefix == ""
    assert settings.catalog_query_prefix == ""
    assert settings.assistant_agent_max_tool_calls_per_turn == 3
    assert settings.assistant_agent_max_iterations == 4
    assert settings.assistant_agent_timeout_seconds == 30.0
    assert settings.rag_answer_timeout_seconds == 60.0
    assert settings.argus_demo_mode is False
    assert settings.argus_demo_catalog_csv_path == REPO_ROOT / "test_files/prices.csv"


def test_settings_parses_catalog_vector_env(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required_env(monkeypatch)
    monkeypatch.setenv("DOCUMENT_QDRANT_COLLECTION", "document_test")
    monkeypatch.setenv("DOCUMENT_EMBEDDING_DIM", "384")
    monkeypatch.setenv("CATALOG_QDRANT_COLLECTION", "catalog_test")
    monkeypatch.setenv("CATALOG_EMBEDDING_MODEL", "catalog-model")
    monkeypatch.setenv("CATALOG_EMBEDDING_DIM", "1024")
    monkeypatch.setenv("CATALOG_EMBEDDING_TEMPLATE_VERSION", "prices_v2")
    monkeypatch.setenv("CATALOG_DOCUMENT_PREFIX", "doc: ")
    monkeypatch.setenv("CATALOG_QUERY_PREFIX", "query: ")

    settings = _settings_without_env_file()

    assert settings.document_qdrant_collection == "document_test"
    assert settings.document_embedding_dim == 384
    assert settings.catalog_qdrant_collection == "catalog_test"
    assert settings.catalog_embedding_model == "catalog-model"
    assert settings.catalog_embedding_dim == 1024
    assert settings.catalog_embedding_template_version == "prices_v2"
    assert settings.catalog_document_prefix == "doc: "
    assert settings.catalog_query_prefix == "query: "


def test_settings_parses_openai_compatible_model_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch)
    monkeypatch.setenv("API_KEY", "secret-token")
    monkeypatch.setenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
    monkeypatch.setenv("CHAT_MODEL", "openai/gpt-oss-120b")

    settings = _settings_without_env_file()

    assert settings.llm_base_url == "https://api.vsellm.ru/v1"
    assert settings.api_key == "secret-token"
    assert settings.embedding_model == "openai/text-embedding-3-small"
    assert settings.chat_model == "openai/gpt-oss-120b"


def test_settings_accepts_legacy_lm_studio_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch)
    monkeypatch.delenv("LLM_BASE_URL")
    monkeypatch.delenv("CHAT_MODEL")
    monkeypatch.setenv("LM_STUDIO_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("LM_STUDIO_EMBEDDING_MODEL", "local-embedding")
    monkeypatch.setenv("LM_STUDIO_LLM_MODEL", "local-chat")

    settings = _settings_without_env_file()

    assert settings.llm_base_url == "http://localhost:1234/v1"
    assert settings.embedding_model == "local-embedding"
    assert settings.chat_model == "local-chat"


def test_settings_parses_demo_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    set_required_env(monkeypatch)
    demo_catalog = tmp_path / "prices-demo.csv"
    monkeypatch.setenv("ARGUS_DEMO_MODE", "true")
    monkeypatch.setenv("ARGUS_DEMO_CATALOG_CSV_PATH", str(demo_catalog))

    settings = _settings_without_env_file()

    assert settings.argus_demo_mode is True
    assert settings.argus_demo_catalog_csv_path == demo_catalog


def test_settings_parses_agent_runtime_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_required_env(monkeypatch)
    monkeypatch.setenv("ASSISTANT_AGENT_MAX_TOOL_CALLS_PER_TURN", "5")
    monkeypatch.setenv("ASSISTANT_AGENT_MAX_ITERATIONS", "6")
    monkeypatch.setenv("ASSISTANT_AGENT_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("RAG_ANSWER_TIMEOUT_SECONDS", "45.5")

    settings = _settings_without_env_file()

    assert settings.assistant_agent_max_tool_calls_per_turn == 5
    assert settings.assistant_agent_max_iterations == 6
    assert settings.assistant_agent_timeout_seconds == 12.5
    assert settings.rag_answer_timeout_seconds == 45.5


def test_settings_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required_env(monkeypatch)
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(ValidationError) as exc_info:
        _settings_without_env_file()

    assert any(error["loc"] == ("database_url",) for error in exc_info.value.errors())


def test_settings_requires_llm_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required_env(monkeypatch)
    monkeypatch.delenv("LLM_BASE_URL")
    monkeypatch.delenv("LM_STUDIO_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        _settings_without_env_file()

    assert any(error["loc"] == ("LLM_BASE_URL",) for error in exc_info.value.errors())


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required_env(monkeypatch)

    first = get_settings()
    second = get_settings()

    assert first is second


def test_settings_env_file_points_to_repo_root() -> None:
    assert Settings.model_config["env_file"] == REPO_ROOT / ".env"


def test_settings_ignores_alembic_database_url_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "DATABASE_URL=postgresql+asyncpg://argus:argus@localhost:5432/argus",
                "ALEMBIC_DATABASE_URL=postgresql+asyncpg://argus:argus@localhost:5432/argus",
                "REDIS_URL=redis://localhost:6379/0",
                "QDRANT_URL=http://localhost:6333",
                "LLM_BASE_URL=https://api.vsellm.ru/v1",
                "CHAT_MODEL=openai/gpt-oss-120b",
            )
        )
    )

    settings = Settings(_env_file=env_file)  # type: ignore[call-arg]

    assert settings.database_url == (
        "postgresql+asyncpg://argus:argus@localhost:5432/argus"
    )
