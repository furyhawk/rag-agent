"""Reranker service orchestrator."""

from __future__ import annotations

from rag_agent.models.search import SearchResult
from rag_agent.rerankers.base import BaseReranker


class RerankService:
    """Orchestrates reranking with lazy model loading."""

    def __init__(self, reranker: BaseReranker) -> None:
        self._reranker = reranker

    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 5
    ) -> list[SearchResult]:
        return await self._reranker.rerank(query, results, top_k)
