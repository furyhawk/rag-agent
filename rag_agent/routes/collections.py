"""Collection management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from rag_agent.core.config import SettingsDep
from rag_agent.core.database import open_session
from rag_agent.core.exceptions import BadRequestError
from rag_agent.models.collection import CollectionCreate
from rag_agent.models.common import DocumentInfo
from rag_agent.schemas.collection import CollectionItem, CollectionListResponse
from rag_agent.schemas.common import MessageResponse
from rag_agent.vectorstore.base import BaseVectorStore
from rag_agent.vectorstore.milvus import MilvusVectorStore
from rag_agent.vectorstore.service import VectorStoreService

router = APIRouter(tags=["collections"])


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


@router.get("/api/v1/collections")
async def list_collections(
    vector_store: BaseVectorStore = Depends(get_vector_store),
) -> CollectionListResponse:
    names = await vector_store.list_collections()
    items = []
    for name in names:
        info = await vector_store.get_collection_info(name)
        items.append(
            CollectionItem(
                name=info.name,
                total_vectors=info.total_vectors,
                dim=info.dim,
                indexing_status=info.indexing_status,
            )
        )
    return CollectionListResponse(items=items, total=len(items))


@router.post("/api/v1/collections")
async def create_collection(
    name: str = Query(..., min_length=1, max_length=64),
    vector_store: BaseVectorStore = Depends(get_vector_store),
) -> MessageResponse:
    try:
        service = VectorStoreService(vector_store)
        await service.ensure_collection(name)
        return MessageResponse(message=f"Collection '{name}' created")
    except Exception as e:
        raise BadRequestError(str(e))


@router.get("/api/v1/collections/{name}")
async def get_collection(
    name: str,
    vector_store: BaseVectorStore = Depends(get_vector_store),
) -> CollectionItem:
    info = await vector_store.get_collection_info(name)
    return CollectionItem(
        name=info.name,
        total_vectors=info.total_vectors,
        dim=info.dim,
        indexing_status=info.indexing_status,
    )


@router.delete("/api/v1/collections/{name}")
async def delete_collection(
    name: str,
    vector_store: BaseVectorStore = Depends(get_vector_store),
) -> MessageResponse:
    await vector_store.delete_collection(name)
    return MessageResponse(message=f"Collection '{name}' deleted")


@router.get("/api/v1/collections/{name}/documents")
async def list_collection_documents(
    name: str,
    vector_store: BaseVectorStore = Depends(get_vector_store),
) -> list[DocumentInfo]:
    return await vector_store.get_documents(name)
