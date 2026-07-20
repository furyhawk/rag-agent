"""Search domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """A single search result from the vector store."""

    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_doc_id: str | None = None
    chunk_id: str | None = None


class SearchRequest(BaseModel):
    """Search request parameters."""

    query: str
    collection_name: str = "documents"
    collection_names: list[str] | None = None
    limit: int = Field(default=5, ge=1, le=50)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    filter: str | None = None
    use_reranker: bool = False
    document_id: str | None = None


class SearchResponse(BaseModel):
    """Search response containing results."""

    results: list[SearchResult]
    query: str
    collection_name: str
    total: int = 0
