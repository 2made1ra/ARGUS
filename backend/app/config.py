from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    qdrant_url: str
    lm_studio_url: str
    lm_studio_embedding_model: str = "nomic-embed-text-v1.5"
    lm_studio_llm_model: str
    upload_dir: Path = Path("/data/uploads")
    qdrant_collection: str = "document_chunks"
    embedding_dim: int = 768

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
