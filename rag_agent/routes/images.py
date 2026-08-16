"""Image serving routes.

Extracted images are persisted to disk during ingestion. These endpoints
serve them to the frontend for display in search results and document views.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from rag_agent.core.config import SettingsDep
from rag_agent.pipeline.file_storage import LocalFileStorage
from rag_agent.schemas.search import SearchResultImage
from rag_agent.vectorstore.base import BaseVectorStore
from rag_agent.vectorstore.milvus import MilvusVectorStore

router = APIRouter(tags=["images"])


async def get_vector_store(settings: SettingsDep) -> BaseVectorStore:
    from rag_agent.embeddings.service import EmbeddingService

    embed_service = EmbeddingService(
        settings=settings.rag,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        models_cache_dir=str(settings.models_cache_dir),
    )
    return MilvusVectorStore(
        milvus_uri=settings.milvus_uri,
        milvus_token=settings.milvus_token,
        embedding_dim=settings.embedding_dim,
        embedding_service=embed_service,
        max_batch_bytes=settings.milvus_max_batch_bytes,
    )


@router.get("/api/v1/images/{image_id}")
async def get_image(
    image_id: str,
    settings: SettingsDep,
    response_format: str = Query(
        default="raw", alias="format", pattern="^(raw|data_uri)$"
    ),
) -> Response:
    """Serve a single persisted image by id.

    Defaults to the raw image bytes so it renders directly in a browser or an
    ``<img src>``. Pass ``?format=data_uri`` to get a base64 data URI string
    like ``data:image/png;base64,<data>`` instead.
    """
    storage = LocalFileStorage(settings.media_dir)
    path = storage.resolve_image(image_id)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    mime_type = storage.mime_type_for(path)
    if response_format == "data_uri":
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return Response(
            content=f"data:{mime_type};base64,{encoded}",
            media_type="text/plain",
        )
    return Response(
        content=path.read_bytes(),
        media_type=mime_type,
    )


@router.get("/api/v1/documents/{document_id}/images")
async def list_document_images(
    document_id: str,
    settings: SettingsDep,
    collection_name: str = Query("documents"),
    vector_store: BaseVectorStore = Depends(get_vector_store),
) -> list[SearchResultImage]:
    """Return image references (with fetch URLs) for one document's chunks."""
    metas = await vector_store.get_document_images(
        collection_name=collection_name,
        document_id=document_id,
    )
    return [
        SearchResultImage(
            image_id=meta["image_id"],
            url=f"/api/v1/images/{meta['image_id']}",
            mime_type=str(meta.get("mime_type", "image/png")),
            page_num=int(meta.get("page_num", 0)),
            width=meta.get("width"),
            height=meta.get("height"),
            description=str(meta.get("description", "")),
        )
        for meta in metas
    ]
