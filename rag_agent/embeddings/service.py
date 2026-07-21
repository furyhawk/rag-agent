"""Embedding service orchestrator with batching and dimension validation."""

from __future__ import annotations

import time

from rag_agent.core.config import RAGSettings
from rag_agent.core.logging import get_logger
from rag_agent.embeddings.base import BaseEmbeddingProvider
from rag_agent.embeddings.local import LocalEmbeddingProvider
from rag_agent.embeddings.openai_compat import OpenAIEmbeddingProvider
from rag_agent.models.document import Document

logger = get_logger(__name__)


class EmbeddingService:
    """Orchestrates embedding operations with batching and validation.

    Improvements over agent_alpha:
    - Batched embedding (configurable batch size, default 100)
    - Retry with exponential backoff
    - Dimension validation on every call
    """

    def __init__(
        self,
        settings: RAGSettings,
        api_key: str | None = None,
        base_url: str | None = None,
        batch_size: int = 100,
        max_retries: int = 3,
        models_cache_dir: str | None = None,
    ) -> None:
        config = settings.embeddings_config
        self.expected_dim = config.dim
        self.batch_size = batch_size
        self.max_retries = max_retries

        if base_url:
            self.provider: BaseEmbeddingProvider = OpenAIEmbeddingProvider(
                model=config.model,
                api_key=api_key,
                base_url=base_url,
            )
            logger.info("embedding.service.provider", provider="openai-compat", base_url=base_url)
        else:
            self.provider = LocalEmbeddingProvider(
                model=config.model,
                cache_dir=models_cache_dir,
            )
            logger.info("embedding.service.provider", provider="local", model=config.model)

    def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        """Embed texts with retry and exponential backoff."""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return self.provider.embed_queries(texts)
            except Exception as e:
                last_error = e
                delay = min(2**attempt, 30.0)
                logger.warning(
                    "embedding.retry",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    delay_s=delay,
                    error=str(e),
                )
                time.sleep(delay)
        raise last_error  # type: ignore[misc]

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query text.

        Raises:
            ValueError: If embedding dimension doesn't match expected.
        """
        result = self._embed_with_retry([query])[0]
        if len(result) != self.expected_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.expected_dim}, "
                f"got {len(result)}. Check your embedding model configuration."
            )
        return result

    def embed_document(self, document: Document) -> list[list[float]]:
        """Embed all chunks of a document in batches.

        Batches at `batch_size` to avoid hitting API token limits.
        """
        chunks = document.chunks or []
        texts = [chunk.chunk_content for chunk in chunks]

        logger.info(
            "embedding.service.document",
            filename=document.metadata.filename,
            chunks=len(texts),
            batch_size=self.batch_size,
            expected_dim=self.expected_dim,
        )

        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            vectors = self._embed_with_retry(batch)
            all_vectors.extend(vectors)

        if all_vectors and len(all_vectors[0]) != self.expected_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.expected_dim}, "
                f"got {len(all_vectors[0])}. Check your embedding model configuration."
            )

        return all_vectors

    def warmup(self) -> None:
        """Ensure the provider is ready."""
        self.provider.warmup()
