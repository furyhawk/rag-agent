"""Retrieval service — multi-stage pipeline.

Extracted and generalized from agent_alpha/backend/services/rag/retrieval.py.
"""

from __future__ import annotations

from typing import Any

from rag_agent.core.config import RAGSettings
from rag_agent.core.logging import get_logger
from rag_agent.models.search import SearchResult
from rag_agent.rerankers.base import CrossEncoderReranker
from rag_agent.rerankers.service import RerankService
from rag_agent.retrieval.bm25 import BM25Searcher
from rag_agent.vectorstore.base import BaseVectorStore

logger = get_logger(__name__)


class RetrievalService:
    """Multi-stage retrieval: vector → BM25 → rerank → filter → dedup."""

    def __init__(
        self,
        settings: RAGSettings,
        vector_store: BaseVectorStore,
        enable_hybrid_search: bool = False,
        use_reranker: bool = False,
    ) -> None:
        self._settings = settings
        self._store = vector_store
        self._enable_hybrid = enable_hybrid_search
        self._use_reranker = use_reranker
        self._reranker = (
            RerankService(CrossEncoderReranker(settings.reranker_config.model))
            if use_reranker
            else None
        )

    @staticmethod
    def _rrf_fusion(
        vector_results: list[SearchResult],
        bm25_results: list[tuple[str, float]],
        k: int = 60,
    ) -> list[SearchResult]:
        """Reciprocal Rank Fusion."""
        rrf_scores: dict[int, float] = {}
        for rank, result in enumerate(vector_results):
            rrf_scores[rank] = 1.0 / (k + rank + 1)
        for rank, (content, _) in enumerate(bm25_results):
            idx = next(
                (i for i, r in enumerate(vector_results) if r.content == content),
                -1,
            )
            if idx >= 0:
                rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (k + rank + 1)
        fused = sorted(
            [(vector_results[i], score) for i, score in rrf_scores.items()],
            key=lambda x: x[1],
            reverse=True,
        )
        return [r for r, _ in fused]

    async def retrieve(
        self,
        collection_name: str,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
        filter: str | None = None,
        use_reranker: bool | None = None,
    ) -> list[SearchResult]:
        """Retrieve relevant results from a single collection."""
        fetch_multiplier = 2 if (use_reranker or self._use_reranker) else 1
        results = await self._store.search(
            collection_name=collection_name,
            query=query,
            limit=limit * fetch_multiplier,
            filter=filter or "",
        )
        logger.info(
            "retrieve.vector",
            query=query,
            collection=collection_name,
            results=len(results),
        )

        # Hybrid BM25 fusion
        if self._enable_hybrid:
            searcher = BM25Searcher()
            contents = [r.content for r in results]
            searcher.index(contents)
            bm25 = searcher.search(query, top_k=len(results))
            results = self._rrf_fusion(results, bm25)

        # Rerank
        if (use_reranker or self._use_reranker) and self._reranker:
            results = await self._reranker.rerank(query, results, top_k=limit)

        # Score filtering
        if min_score > 0:
            results = [r for r in results if r.score >= min_score]

        # Dedup by parent_doc_id
        seen = set()
        deduped: list[SearchResult] = []
        for r in results:
            key = f"{r.parent_doc_id}:{r.metadata.get('page_num')}:{r.metadata.get('chunk_num')}"
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        results = deduped[:limit]

        return results

    async def retrieve_multi(
        self,
        collection_names: list[str],
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """Retrieve across multiple collections, merge and dedup."""
        all_results: list[SearchResult] = []
        for name in collection_names:
            results = await self.retrieve(
                name, query, limit=limit, min_score=min_score
            )
            for r in results:
                r.metadata["collection"] = name
            all_results.extend(results)

        # Sort by score, dedup
        all_results.sort(key=lambda x: x.score, reverse=True)
        seen = set()
        deduped: list[SearchResult] = []
        for r in all_results:
            key = f"{r.parent_doc_id}:{r.metadata.get('page_num')}:{r.metadata.get('chunk_num')}"
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        return deduped[:limit]
