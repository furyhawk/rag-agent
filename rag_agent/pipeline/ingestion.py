"""Ingestion service — orchestrates the full pipeline.

Extracted and generalized from agent_alpha/backend/services/rag/ingestion.py.
Improvements: progress callbacks, indexed dedup via DB.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from rag_agent.core.config import RAGSettings
from rag_agent.core.logging import get_logger
from rag_agent.embeddings.service import EmbeddingService
from rag_agent.models.ingestion import IngestionResult, IngestionStatus
from rag_agent.models.document import Document
from rag_agent.pipeline.processor import DocumentProcessor
from rag_agent.vectorstore.base import BaseVectorStore

logger = get_logger(__name__)

ProgressCallback = Callable[[IngestionStatus, int, int], Awaitable[None]]


class IngestionService:
    """Orchestrates the data flow:
    File Path → Parse/Chunk → Deduplicate → Embed/Store → Query-Ready
    """

    def __init__(
        self,
        processor: DocumentProcessor,
        vector_store: BaseVectorStore,
        on_event: Callable[..., Awaitable[None]] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.processor = processor
        self.store = vector_store
        self._on_event = on_event
        self._progress = progress_callback

    @classmethod
    def build(
        cls,
        settings: RAGSettings,
        milvus_uri: str,
        milvus_token: str,
        embedding_api_key: str | None = None,
        embedding_base_url: str | None = None,
        models_cache_dir: str | None = None,
        on_event: Callable[..., Awaitable[None]] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> IngestionService:
        """Construct an IngestionService from application settings."""
        from rag_agent.vectorstore.milvus import MilvusVectorStore

        embed_service = EmbeddingService(
            settings=settings,
            api_key=embedding_api_key,
            base_url=embedding_base_url,
            models_cache_dir=models_cache_dir,
        )
        vector_store = MilvusVectorStore(
            milvus_uri=milvus_uri,
            milvus_token=milvus_token,
            embedding_dim=settings.embeddings_config.dim,
            embedding_service=embed_service,
        )
        processor = DocumentProcessor(settings=settings)
        return cls(
            processor=processor,
            vector_store=vector_store,
            on_event=on_event,
            progress_callback=progress_callback,
        )

    async def _emit(self, event: str, data: dict) -> None:
        if self._on_event:
            try:
                await self._on_event(event, data)
            except Exception as e:
                logger.warning("Event dispatch failed", exc_info=e)

    async def _notify(
        self,
        status: IngestionStatus,
        pages: int = 0,
        chunks: int = 0,
    ) -> None:
        if self._progress:
            await self._progress(status, pages, chunks)

    async def _find_existing_by_source(
        self, collection_name: str, source_path: str
    ) -> str | None:
        """Find existing document by source_path."""
        try:
            docs = await self.store.get_documents(collection_name)
            for doc in docs:
                meta = doc.additional_info or {}
                if meta.get("source_path") == source_path:
                    return doc.document_id
            for doc in docs:
                if doc.filename and doc.filename == Path(source_path).name:
                    return doc.document_id
        except Exception:
            pass
        return None

    async def _find_existing_by_hash(
        self, collection_name: str, content_hash: str
    ) -> str | None:
        """Find existing document by content hash (exact duplicate)."""
        try:
            docs = await self.store.get_documents(collection_name)
            for doc in docs:
                meta = doc.additional_info or {}
                if meta.get("content_hash") == content_hash:
                    return doc.document_id
        except Exception:
            pass
        return None

    async def ingest_file(
        self,
        filepath: Path,
        collection_name: str,
        replace: bool = True,
        source_path: str = "",
    ) -> IngestionResult:
        """Process a file and push it into the vector database.

        Args:
            filepath: Path to the file to process.
            collection_name: Target collection name.
            replace: If True, replace existing document with same source.
            source_path: Override source path (e.g., s3://bucket/key).
        """
        try:
            logger.info(
                "ingest.start",
                filename=filepath.name,
                collection=collection_name,
                replace=replace,
            )

            # 1. Parse + Chunk
            await self._notify(IngestionStatus.PARSING)
            document: Document = await self.processor.process_file(filepath)

            # Override source_path if provided
            if source_path:
                document.metadata.source_path = source_path
                document.metadata.filename = Path(source_path).name

            chunk_count = len(document.chunks or [])
            await self._notify(
                IngestionStatus.CHUNKING,
                pages=document.num_pages,
                chunks=chunk_count,
            )

            # 2. Deduplication
            existing_id = None
            if replace:
                if document.metadata.source_path:
                    existing_id = await self._find_existing_by_source(
                        collection_name, document.metadata.source_path
                    )
                if not existing_id and document.metadata.content_hash:
                    existing_id = await self._find_existing_by_hash(
                        collection_name, document.metadata.content_hash
                    )

            if existing_id:
                await self.store.delete_document(
                    collection_name, existing_id
                )
                logger.info(
                    "ingest.replaced",
                    old_id=existing_id,
                    filename=filepath.name,
                )

            # 3. Embed + Store
            await self._notify(IngestionStatus.EMBEDDING)
            await self.store.insert_document(
                collection_name=collection_name,
                document=document,
            )
            await self._notify(IngestionStatus.STORING, chunks=chunk_count)

            action = "replaced" if existing_id else "ingested"
            await self._emit(
                "rag.document.ingested",
                {
                    "document_id": document.id,
                    "filename": filepath.name,
                    "collection": collection_name,
                    "action": action,
                    "chunks": chunk_count,
                    "source_path": document.metadata.source_path,
                },
            )

            logger.info(
                "ingest.complete",
                action=action,
                doc_id=document.id,
                chunks=chunk_count,
            )

            return IngestionResult(
                status=IngestionStatus.DONE,
                document_id=document.id,
                message=f"Successfully {action} '{filepath.name}'",
                chunk_count=chunk_count,
            )

        except Exception as e:
            logger.error("ingest.error", filename=filepath.name, error=str(e))
            return IngestionResult(
                status=IngestionStatus.ERROR,
                error_message=str(e),
                message=f"Failed to process {filepath.name}",
            )

    async def find_existing(
        self, collection_name: str, source_path: str
    ) -> str | None:
        return await self._find_existing_by_source(
            collection_name, source_path
        )

    async def remove_document(
        self, collection_name: str, document_id: str
    ) -> bool:
        try:
            await self.store.delete_document(
                collection_name=collection_name,
                document_id=document_id,
            )
            await self._emit(
                "rag.document.deleted",
                {"document_id": document_id, "collection": collection_name},
            )
            return True
        except Exception as e:
            logger.error(
                "ingest.delete_failed", document_id=document_id, error=str(e)
            )
            return False
