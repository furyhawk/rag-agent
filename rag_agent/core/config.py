"""Application configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Known embedding models and their output dimensions.
EMBEDDING_DIMENSIONS: dict[str, int] = {
    # OpenAI
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    # Voyage AI
    "voyage-3": 1024,
    "voyage-3-lite": 512,
    "voyage-code-3": 1024,
    # Google Gemini
    "gemini-embedding-exp-03-07": 3072,
    # SentenceTransformers (local)
    "all-MiniLM-L6-v2": 384,
    "codefuse-ai/F2LLM-v2-80M": 320,
    "all-mpnet-base-v2": 768,
    "bge-small-en-v1.5": 384,
    "bge-base-en-v1.5": 768,
    "bge-large-en-v1.5": 1024,
    # Jina AI Omni (text + image + video + audio)
    "jinaai/jina-embeddings-v5-omni-nano": 768,
    "jinaai/jina-embeddings-v5-omni-small": 1024,
}


class EmbeddingsConfig(BaseModel):
    """Embedding model configuration with auto-derived dimension."""

    model: str = "all-MiniLM-L6-v2"
    dim: int = 384

    @model_validator(mode="after")
    def _set_dim_from_model(self) -> "EmbeddingsConfig":
        if self.model in EMBEDDING_DIMENSIONS:
            self.dim = EMBEDDING_DIMENSIONS[self.model]
        return self


class RerankerConfig(BaseModel):
    """Reranker configuration."""

    model: str = "cross_encoder"


class RAGSettings(BaseModel):
    """RAG pipeline settings derived from application Settings."""

    collection_name: str = "documents"
    chunk_size: int = 512
    chunk_overlap: int = 50
    chunking_strategy: str = "recursive"
    enable_hybrid_search: bool = False
    enable_ocr: bool = False
    enable_image_description: bool = True
    embeddings_config: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    reranker_config: RerankerConfig = Field(default_factory=RerankerConfig)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Infrastructure ────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://rag:rag@localhost:5433/rag"
    valkey_url: str = "redis://localhost:6379/0"
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = ""

    # ── Embeddings ────────────────────────────────────────────────
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # ── LLM (image description) ──────────────────────────────────
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # ── Storage ──────────────────────────────────────────────────
    media_dir: str = "/data/media"
    max_upload_size_mb: int = 50

    # ── Pipeline ─────────────────────────────────────────────────
    chunk_size: int = 512
    chunk_overlap: int = 50
    chunking_strategy: str = "recursive"
    enable_hybrid_search: bool = False
    enable_ocr: bool = False
    enable_image_description: bool = True

    # ── Reranker ─────────────────────────────────────────────────
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    hf_token: str = ""
    models_cache_dir: Path = Path.home() / ".cache" / "rag-agent" / "models"

    # ── Worker ───────────────────────────────────────────────────
    worker_job_timeout: int = 3600  # seconds per ARQ job (Milvus flush can be slow)

    # ── Server ───────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8100
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    log_level: str = "INFO"
    log_format: str = "json"

    @property
    def rag(self) -> RAGSettings:
        """Build RAG pipeline settings from application settings."""
        return RAGSettings(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            chunking_strategy=self.chunking_strategy,
            enable_hybrid_search=self.enable_hybrid_search,
            enable_ocr=self.enable_ocr,
            enable_image_description=self.enable_image_description,
            embeddings_config=EmbeddingsConfig(
                model=self.embedding_model,
                dim=self.embedding_dim,
            ),
            reranker_config=RerankerConfig(model=self.cross_encoder_model),
        )

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


def get_settings() -> Settings:
    """Create settings instance."""
    return Settings()


# Dependency injection type alias — defined here to avoid circular imports with deps.py
from typing import Annotated  # noqa: E402
from fastapi import Depends  # noqa: E402

SettingsDep = Annotated[Settings, Depends(get_settings)]
