"""BM25 keyword search helper."""

from __future__ import annotations

from typing import Any

from rank_bm25 import BM25Okapi


class BM25Searcher:
    """BM25 search for hybrid retrieval fusion."""

    def __init__(self) -> None:
        self._bm25 = None
        self._contents: list[str] = []

    def index(self, contents: list[str]) -> None:
        self._contents = contents
        tokenized = [c.lower().split() for c in contents]
        self._bm25 = BM25Okapi(tokenized)

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        if not self._bm25:
            return []
        tokenized_query = query.lower().split()
        scores = self._bm25.get_scores(tokenized_query)
        scored = list(zip(self._contents, scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
