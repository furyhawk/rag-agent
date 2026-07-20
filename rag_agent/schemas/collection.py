"""Collection API schemas."""

from __future__ import annotations

from pydantic import BaseModel


class CollectionItem(BaseModel):
    """Collection in list views."""

    name: str
    total_vectors: int
    dim: int
    indexing_status: str = "complete"


class CollectionListResponse(BaseModel):
    """List of collections."""

    items: list[CollectionItem]
    total: int
