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
        self._using_cpu_fallback = False

    @staticmethod
    def _is_triton_compiler_error(error: Exception) -> bool:
        msg = str(error)
        return (
            "Failed to find C compiler" in msg
            or "triton.knobs.build.impl" in msg
        )

    def _load_model(self, device: str | None = None) -> None:
        """Lazy-load the cross-encoder model.

        ``device="cpu"`` is used for the Triton-compiler fallback path (hosts
        without a C toolchain can fail when torch JIT-compiles attention
        kernels on CUDA).
        """
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name, device=device)
            logger.info("reranker.loaded", model=self._model_name, device=device)

    def warmup(self) -> None:
        self._load_model()

    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 5
    ) -> list[SearchResult]:
        self._load_model()
        pairs = [(query, r.content) for r in results]
        try:
            scores = self._model.predict(pairs)  # type: ignore
        except Exception as exc:
            if self._using_cpu_fallback or not self._is_triton_compiler_error(exc):
                raise
            logger.warning(
                "reranker.triton_fallback",
                model=self._model_name,
                error=str(exc),
            )
            self._using_cpu_fallback = True
            self._model = None
            self._load_model(device="cpu")
            scores = self._model.predict(pairs)  # type: ignore
        scored = [(r, float(s)) for r, s in zip(results, scores)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, s in scored[:top_k]]
