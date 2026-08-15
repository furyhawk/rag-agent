"""Unit tests for extracted-image persistence, metadata, and serving."""

from __future__ import annotations

from pathlib import Path

import pytest

from rag_agent.core.config import Settings
from rag_agent.models.document import Document, DocumentChunk, DocumentImage, DocumentMetadata
from rag_agent.pipeline.file_storage import LocalFileStorage
from rag_agent.routes.images import get_image
from rag_agent.vectorstore.base import BaseVectorStore

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def storage(tmp_path: Path) -> LocalFileStorage:
    return LocalFileStorage(tmp_path / "media")


@pytest.mark.asyncio
async def test_save_and_resolve_image(storage: LocalFileStorage) -> None:
    path = await storage.save_image(
        image_id="img-123",
        data=PNG_BYTES,
        mime_type="image/png",
        collection="docs",
        document_id="doc-1",
    )
    assert path.exists()
    assert path.name == "img-123.png"
    # Stored under <base>/images/<collection>/<document_id>/
    assert "images" in path.parts
    assert "docs" in path.parts
    assert "doc-1" in path.parts

    resolved = storage.resolve_image("img-123")
    assert resolved == path
    assert storage.mime_type_for(resolved) == "image/png"
    assert resolved.read_bytes() == PNG_BYTES


@pytest.mark.asyncio
async def test_resolve_image_missing_or_unsafe(storage: LocalFileStorage) -> None:
    assert storage.resolve_image("does-not-exist") is None
    # Path traversal / unsafe ids are rejected.
    assert storage.resolve_image("../etc/passwd") is None
    assert storage.resolve_image("") is None


@pytest.mark.asyncio
async def test_jpeg_extension_and_mime(storage: LocalFileStorage) -> None:
    path = await storage.save_image(
        image_id="img-jpg",
        data=b"\xff\xd8\xff\xe0" + b"\x00" * 8,
        mime_type="image/jpeg",
        collection="docs",
        document_id="doc-1",
    )
    assert path.name == "img-jpg.jpg"
    assert storage.mime_type_for(path) == "image/jpeg"


@pytest.mark.asyncio
async def test_delete_document_images(storage: LocalFileStorage) -> None:
    await storage.save_image(
        image_id="a", data=PNG_BYTES, mime_type="image/png",
        collection="docs", document_id="doc-1",
    )
    await storage.save_image(
        image_id="b", data=PNG_BYTES, mime_type="image/png",
        collection="docs", document_id="doc-1",
    )
    assert storage.resolve_image("a") is not None
    await storage.delete_document_images("docs", "doc-1")
    assert storage.resolve_image("a") is None
    assert storage.resolve_image("b") is None


def test_build_chunk_metadata_includes_images() -> None:
    image = DocumentImage(
        image_id="img-1",
        page_num=2,
        image_bytes=PNG_BYTES,
        description="A bar chart of quarterly revenue",
        mime_type="image/png",
        width=640,
        height=480,
    )
    chunk = DocumentChunk(
        chunk_content="Some text",
        page_num=2,
        parent_doc_id="doc-1",
        images=[image],
    )
    document = Document(
        pages=[],
        chunks=[chunk],
        metadata=DocumentMetadata(filename="r.pdf", filesize=1, filetype="pdf"),
    )

    meta = BaseVectorStore.build_chunk_metadata(None, chunk, document)  # type: ignore[arg-type]

    assert meta["has_images"] is True
    assert meta["image_count"] == 1
    images = meta["images"]
    assert len(images) == 1
    assert images[0]["image_id"] == "img-1"
    assert images[0]["description"] == "A bar chart of quarterly revenue"
    assert images[0]["page_num"] == 2
    # Raw bytes must never be stored in Milvus metadata.
    assert "image_bytes" not in images[0]


@pytest.mark.asyncio
async def test_get_image_route_serves_persisted_image(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path / "media")
    await storage.save_image(
        image_id="img-serve",
        data=PNG_BYTES,
        mime_type="image/png",
        collection="docs",
        document_id="doc-1",
    )
    settings = Settings(media_dir=str(tmp_path / "media"))

    from fastapi import HTTPException

    import base64

    response = await get_image("img-serve", settings)
    assert response.status_code == 200
    assert response.media_type == "text/plain"
    expected = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode("ascii")
    assert response.body.decode() == expected

    with pytest.raises(HTTPException) as exc:
        await get_image("img-missing", settings)
    assert exc.value.status_code == 404
