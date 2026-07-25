"""Local embedding provider using sentence-transformers.

Downloads and runs models locally via the sentence-transformers library.
Used when EMBEDDING_BASE_URL is empty (no remote endpoint configured).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from rag_agent.core.logging import get_logger
from rag_agent.embeddings.base import BaseEmbeddingProvider
from rag_agent.models.document import Document

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = get_logger(__name__)


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """Embedding provider that runs a sentence-transformers model locally."""

    def __init__(self, model: str, cache_dir: str | None = None) -> None:
        self.model_name = model
        self._model: Any | None = None
        self.cache_dir = cache_dir

    @property
    def model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "Local embeddings require sentence-transformers. "
                    "Install with: pip install 'verity-rag[local-ml]'"
                ) from exc
            logger.info(
                "embedding.local.load",
                model=self.model_name,
            )
            self._model = SentenceTransformer(
                self.model_name,
                cache_folder=self.cache_dir,
            )
        return self._model

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return embeddings.tolist() if isinstance(embeddings, np.ndarray) else [e.tolist() for e in embeddings]

    def embed_document(self, document: Document) -> list[list[float]]:
        texts = [
            chunk.chunk_content
            for chunk in (document.chunks or [])
        ]
        logger.info(
            "embedding.local.document",
            filename=document.metadata.filename,
            chunks=len(texts),
            model=self.model_name,
        )
        return self.embed_queries(texts)

    def warmup(self) -> None:
        """Preload the model."""
        _ = self.model
