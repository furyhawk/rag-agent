"""Search routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from rag_agent.core.config import SettingsDep
from rag_agent.core.database import open_session
from rag_agent.models.common import DocumentInfo
from rag_agent.retrieval.service import RetrievalService
from rag_agent.schemas.search import (
    MultiSearchResponse,
    SearchRequest,
    SearchResponse,
    SearchResultImage,
    SearchResultItem,
)
from rag_agent.vectorstore.base import BaseVectorStore
from rag_agent.vectorstore.milvus import MilvusVectorStore

router = APIRouter(tags=["search"])


def _result_images(metadata: dict) -> list[SearchResultImage]:
    """Build image references (with fetch URLs) from chunk metadata."""
    items: list[SearchResultImage] = []
    for img in metadata.get("images") or []:
        image_id = str(img.get("image_id", ""))
        if not image_id:
            continue
        items.append(
            SearchResultImage(
                image_id=image_id,
                url=f"/api/v1/images/{image_id}",
                mime_type=str(img.get("mime_type", "image/png")),
                page_num=int(img.get("page_num", 0)),
                width=img.get("width"),
                height=img.get("height"),
                description=str(img.get("description", "")),
            )
        )
    return items


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


@router.post("/api/v1/search")
async def search(
    request: SearchRequest,
    settings: SettingsDep,
    vector_store: BaseVectorStore = Depends(get_vector_store),
) -> SearchResponse:
    retrieval = RetrievalService(
        settings=settings.rag,
        vector_store=vector_store,
        enable_hybrid_search=settings.enable_hybrid_search,
        use_reranker=request.use_reranker,
    )
    results = await retrieval.retrieve(
        collection_name=request.collection_name,
        query=request.query,
        limit=request.limit,
        min_score=request.min_score,
        filter=request.filter,
    )
    return SearchResponse(
        results=[
            SearchResultItem(
                content=r.content,
                score=r.score,
                metadata=r.metadata,
                parent_doc_id=r.parent_doc_id,
                chunk_id=r.chunk_id,
                images=_result_images(r.metadata),
            )
            for r in results
        ],
        query=request.query,
        collection_name=request.collection_name,
        total=len(results),
    )


@router.post("/api/v1/search/multi")
async def search_multi(
    request: SearchRequest,
    settings: SettingsDep,
    vector_store: BaseVectorStore = Depends(get_vector_store),
) -> MultiSearchResponse:
    if not request.collection_names:
        raise ValueError("collection_names required for multi-search")
    retrieval = RetrievalService(
        settings=settings.rag,
        vector_store=vector_store,
        enable_hybrid_search=settings.enable_hybrid_search,
    )
    results = await retrieval.retrieve_multi(
        collection_names=request.collection_names,
        query=request.query,
        limit=request.limit,
        min_score=request.min_score,
    )
    return MultiSearchResponse(
        results=[
            SearchResultItem(
                content=r.content,
                score=r.score,
                metadata=r.metadata,
                parent_doc_id=r.parent_doc_id,
                chunk_id=r.chunk_id,
                images=_result_images(r.metadata),
            )
            for r in results
        ],
        query=request.query,
        collections=request.collection_names,
        total=len(results),
    )


@router.get("/api/v1/collections/{collection_name}/documents/{document_id}")
async def search_by_document(
    collection_name: str,
    document_id: str,
    query: str,
    settings: SettingsDep,
    limit: int = 5,
    vector_store: BaseVectorStore = Depends(get_vector_store),
) -> SearchResponse:
    retrieval = RetrievalService(
        settings=settings.rag,
        vector_store=vector_store,
    )
    filter_expr = f'parent_doc_id == "{document_id}"'
    results = await retrieval.retrieve(
        collection_name=collection_name,
        query=query,
        limit=limit,
        filter=filter_expr,
    )
    return SearchResponse(
        results=[
            SearchResultItem(
                content=r.content,
                score=r.score,
                metadata=r.metadata,
                parent_doc_id=r.parent_doc_id,
                chunk_id=r.chunk_id,
                images=_result_images(r.metadata),
            )
            for r in results
        ],
        query=query,
        collection_name=collection_name,
        total=len(results),
    )
