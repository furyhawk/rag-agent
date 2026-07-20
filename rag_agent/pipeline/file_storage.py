"""File storage abstraction for uploaded documents."""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path


class BaseFileStorage(ABC):
    """Abstract base for file storage backends."""

    @abstractmethod
    async def save(
        self, filename: str, data: bytes, collection: str = "documents"
    ) -> Path:
        """Save uploaded file data. Returns the storage path."""
        ...

    @abstractmethod
    async def delete(self, path: Path) -> None:
        """Delete a stored file."""
        ...

    @abstractmethod
    async def read(self, path: Path) -> bytes:
        """Read file data from storage."""
        ...


class LocalFileStorage(BaseFileStorage):
    """Local filesystem storage for uploaded documents."""

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)

    def _collection_dir(self, collection: str) -> Path:
        d = self._base / "rag" / collection
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def save(
        self, filename: str, data: bytes, collection: str = "documents"
    ) -> Path:
        import uuid

        storage_name = f"{uuid.uuid4().hex}_{filename}"
        path = self._collection_dir(collection) / storage_name
        path.write_bytes(data)
        return path

    async def delete(self, path: Path) -> None:
        if path.exists():
            path.unlink()

    async def read(self, path: Path) -> bytes:
        return path.read_bytes()
