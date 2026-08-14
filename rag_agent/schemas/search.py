"""Search API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Search request."""

    query: str
    collection_name: str = "documents"
    collection_names: list[str] | None = None
    limit: int = Field(default=5, ge=1, le=50)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    filter: str | None = None
    use_reranker: bool = False
    document_id: str | None = None


class SearchResultImage(BaseModel):
    """Reference to an image attached to a search result."""

    image_id: str
    url: str
    mime_type: str = "image/png"
    page_num: int = 0
    width: int | None = None
    height: int | None = None
    description: str = ""


class SearchResultItem(BaseModel):
    """Single search result."""

    content: str
    score: float
    metadata: dict[str, Any]
    parent_doc_id: str | None = None
    chunk_id: str | None = None
    images: list[SearchResultImage] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Search response."""

    results: list[SearchResultItem]
    query: str
    collection_name: str
    total: int = 0


class MultiSearchResponse(BaseModel):
    """Multi-collection search response."""

    results: list[SearchResultItem]
    query: str
    collections: list[str]
    total: int = 0
