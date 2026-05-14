from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    qdrant_url: str
    lm_studio_url: str
    lm_studio_embedding_model: str = "nomic-embed-text-v1.5"
    lm_studio_llm_model: str
    upload_dir: Path = Path("/data/uploads")
    document_qdrant_collection: str = "document_chunks"
    document_embedding_dim: int = 768
    catalog_qdrant_collection: str = "price_items_search_v1"
    catalog_embedding_model: str = "nomic-embed-text-v1.5"
    catalog_embedding_dim: int = 768
    catalog_embedding_template_version: str = "prices_v1"
    catalog_document_prefix: str = "search_document: "
    catalog_query_prefix: str = "search_query: "
    rag_similarity_top_k: int = 15
    rag_context_top_k: int = 5
    rag_reranker_enabled: bool = False
    argus_demo_mode: bool = False
    argus_demo_catalog_csv_path: Path = REPO_ROOT / "test_files/prices.csv"

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
