from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    qdrant_url: str
    llm_base_url: str = Field(
        validation_alias=AliasChoices("LLM_BASE_URL", "LM_STUDIO_URL"),
    )
    api_key: str | None = Field(default=None, validation_alias="API_KEY")
    embedding_model: str = Field(
        default="openai/text-embedding-3-small",
        validation_alias=AliasChoices("EMBEDDING_MODEL", "LM_STUDIO_EMBEDDING_MODEL"),
    )
    chat_model: str = Field(
        default="openai/gpt-oss-120b",
        validation_alias=AliasChoices("CHAT_MODEL", "LM_STUDIO_LLM_MODEL"),
    )
    upload_dir: Path = Path("/data/uploads")
    document_qdrant_collection: str = "document_chunks"
    document_embedding_dim: int = 768
    catalog_qdrant_collection: str = "price_items_search_v1"
    catalog_embedding_model: str = "text-embedding-3-small"
    catalog_embedding_dim: int = 1536
    catalog_embedding_template_version: str = "legacy_csv_embedding"
    catalog_document_prefix: str = ""
    catalog_query_prefix: str = ""
    assistant_agent_max_tool_calls_per_turn: int = 3
    assistant_agent_max_iterations: int = 4
    assistant_agent_timeout_seconds: float = 30.0
    rag_answer_timeout_seconds: float = 60.0
    rag_similarity_top_k: int = 15
    rag_context_top_k: int = 5
    argus_demo_mode: bool = False
    argus_demo_catalog_csv_path: Path = REPO_ROOT / "test_files/prices.csv"

    @property
    def lm_studio_url(self) -> str:
        return self.llm_base_url

    @property
    def lm_studio_embedding_model(self) -> str:
        return self.embedding_model

    @property
    def lm_studio_llm_model(self) -> str:
        return self.chat_model

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
