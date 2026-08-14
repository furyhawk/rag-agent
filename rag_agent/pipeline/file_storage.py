"""File storage abstraction for uploaded documents and extracted images."""

from __future__ import annotations

import re
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

# MIME type <-> file extension mapping for extracted images.
_MIME_TO_EXT: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
    "image/tiff": "tiff",
}
_EXT_TO_MIME: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
}

# image_ids are UUIDs (hex + dashes); only allow safe characters.
_SAFE_IMAGE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


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

    # ── Extracted image storage ────────────────────────────────

    def _document_images_dir(
        self, collection: str, document_id: str
    ) -> Path:
        """Directory holding all extracted images for one document."""
        d = self._base / "images" / collection / document_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def save_image(
        self,
        image_id: str,
        data: bytes,
        mime_type: str,
        collection: str,
        document_id: str,
    ) -> Path:
        """Persist an extracted image. Returns the storage path."""
        ext = _MIME_TO_EXT.get(mime_type, "png")
        path = self._document_images_dir(collection, document_id) / (
            f"{image_id}.{ext}"
        )
        path.write_bytes(data)
        return path

    async def delete_document_images(
        self, collection: str, document_id: str
    ) -> None:
        """Remove all stored images for a document."""
        d = self._base / "images" / collection / document_id
        if d.exists():
            shutil.rmtree(d)

    def resolve_image(self, image_id: str) -> Path | None:
        """Find the stored file for an image id (by scanning the images dir).

        Returns the first matching path or None if not found.
        """
        if not image_id or not _SAFE_IMAGE_ID_RE.match(image_id):
            return None
        base = self._base / "images"
        if not base.exists():
            return None
        matches = sorted(base.rglob(f"{image_id}.*"))
        return matches[0] if matches else None

    @staticmethod
    def mime_type_for(path: Path) -> str:
        """Return the MIME type for a stored image path."""
        ext = path.suffix.lower().lstrip(".")
        return _EXT_TO_MIME.get(ext, "application/octet-stream")
