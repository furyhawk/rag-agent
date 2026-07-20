"""Collection domain models."""

from __future__ import annotations

from pydantic import BaseModel


class CollectionInfo(BaseModel):
    """Information about a vector store collection."""

    name: str
    total_vectors: int
    dim: int
    indexing_status: str = "complete"


class CollectionCreate(BaseModel):
    """Request to create a new collection."""

    name: str
