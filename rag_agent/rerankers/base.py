"""Reranker base and cross-encoder implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod

from rag_agent.core.logging import get_logger
from rag_agent.models.search import SearchResult

logger = get_logger(__name__)


class BaseReranker(ABC):
    """Abstract base for reranking implementations."""

    @abstractmethod
    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 5
    ) -> list[SearchResult]:
        """Rerank results based on query relevance."""
        ...

    @abstractmethod
    def warmup(self) -> None:
        """Ensure model is loaded."""
        ...


class CrossEncoderReranker(BaseReranker):
    """Cross-encoder reranker using Sentence Transformers."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model = None

    def _load_model(self) -> None:
        """Lazy-load the cross-encoder model."""
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
            logger.info("reranker.loaded", model=self._model_name)

    def warmup(self) -> None:
        self._load_model()

    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 5
    ) -> list[SearchResult]:
        self._load_model()
        pairs = [(query, r.content) for r in results]
        scores = self._model.predict(pairs)  # type: ignore
        scored = [(r, float(s)) for r, s in zip(results, scores)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, s in scored[:top_k]]
