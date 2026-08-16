"""Base vector store interface."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from rag_agent.models.collection import CollectionInfo
from rag_agent.models.common import DocumentInfo
from rag_agent.models.document import Document, DocumentChunk
from rag_agent.models.search import SearchResult

_COLLECTION_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")
_RESERVED_COLLECTION_NAMES = frozenset({"all"})

# Milvus JSON field max length (from the server) is 65536. Cap the serialized
# chunk metadata well below that, leaving headroom for gRPC/JSON escaping.
MAX_METADATA_JSON_LENGTH = 60000
# Long string values in metadata are truncated to this many chars.
_MAX_METADATA_STRING_LENGTH = 500


def _truncate_strings(obj: Any, max_len: int = _MAX_METADATA_STRING_LENGTH) -> None:
    """Recursively truncate over-long string values in a dict/list tree."""
    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if isinstance(value, str):
                if len(value) > max_len:
                    obj[key] = value[:max_len] + "..."
            elif isinstance(value, (dict, list)):
                _truncate_strings(value, max_len)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            if isinstance(value, str):
                if len(value) > max_len:
                    obj[i] = value[:max_len] + "..."
            elif isinstance(value, (dict, list)):
                _truncate_strings(value, max_len)


def _metadata_size(meta: dict[str, Any]) -> int:
    """UTF-8 byte length of the JSON-serialized metadata."""
    return len(json.dumps(meta, default=str, ensure_ascii=False).encode("utf-8"))


def _chunk_additional_info(
    additional_info: Any, page_num: int
) -> dict[str, Any] | None:
    """Trim document-level additional_info down to the chunk's own page.

    marker's ``page_stats`` is a list of ALL pages' stats; carrying the
    whole list into every chunk's metadata blows past Milvus's JSON length
    limit. Keep the (small) ToC but replace ``page_stats`` with just this
    chunk's page entry.
    """
    if not isinstance(additional_info, dict):
        return None

    info = dict(additional_info)
    page_stats = info.get("page_stats")
    if isinstance(page_stats, list):
        target_id = page_num - 1  # marker page_id is 0-based
        own = next(
            (
                s
                for s in page_stats
                if isinstance(s, dict) and s.get("page_id") == target_id
            ),
            None,
        )
        if own is None and 0 <= target_id < len(page_stats):
            own = page_stats[target_id]
        if own is not None:
            info["page_stats"] = own
        else:
            info.pop("page_stats", None)
    return info


def _cap_metadata_size(
    meta: dict[str, Any],
    limit: int = MAX_METADATA_JSON_LENGTH,
) -> dict[str, Any]:
    """Guarantee the serialized metadata stays under Milvus's JSON limit.

    Progressive fallbacks: drop heavyweight document-level keys -> truncate
    long strings -> drop ``additional_info`` entirely. ``meta`` is mutated
    in place and returned.
    """
    if _metadata_size(meta) <= limit:
        return meta

    # 1) Drop heavyweight document-level keys from additional_info.
    info = meta.get("additional_info")
    if isinstance(info, dict):
        for key in ("page_stats", "toc"):
            info.pop(key, None)
        if _metadata_size(meta) <= limit:
            return meta

    # 2) Truncate over-long string values anywhere in the tree.
    _truncate_strings(meta)
    if _metadata_size(meta) <= limit:
        return meta

    # 3) Last resort: drop additional_info entirely.
    meta.pop("additional_info", None)
    return meta


class BaseVectorStore(ABC):
    """Abstract base class for vector store implementations."""

    @abstractmethod
    async def ensure_collection(self, name: str) -> None:
        """Create the collection if it does not already exist."""
        ...

    @abstractmethod
    async def insert_document(
        self, collection_name: str, document: Document
    ) -> None:
        """Embed and store document chunks."""
        ...

    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query: str,
        limit: int = 4,
        filter: str = "",
    ) -> list[SearchResult]:
        """Retrieve similar chunks based on a text query."""
        ...

    @abstractmethod
    async def delete_collection(self, collection_name: str) -> None:
        """Remove a collection and all its data."""
        ...

    @abstractmethod
    async def delete_document(
        self, collection_name: str, document_id: str
    ) -> None:
        """Remove all chunks associated with a document ID."""
        ...

    @abstractmethod
    async def get_collection_info(
        self, collection_name: str
    ) -> CollectionInfo:
        """Return metadata and stats about a collection."""
        ...

    @abstractmethod
    async def list_collections(self) -> list[str]:
        """Return list of all collection names."""
        ...

    @abstractmethod
    async def get_documents(
        self, collection_name: str
    ) -> list[DocumentInfo]:
        """Return list of unique documents in a collection."""
        ...

    @abstractmethod
    async def get_document_images(
        self, collection_name: str, document_id: str
    ) -> list[dict[str, Any]]:
        """Return image references for a document's chunks (deduplicated)."""
        ...

    def validate_collection_name(self, name: str) -> None:
        """Validate collection name format.

        Raises:
            ValueError: If name is invalid or reserved.
        """
        if not _COLLECTION_NAME_RE.match(name):
            raise ValueError(
                "Collection name must start with a letter and contain only "
                "letters, numbers, and underscores (max 64 chars)"
            )
        if name.lower() in _RESERVED_COLLECTION_NAMES:
            raise ValueError(f"'{name}' is a reserved collection name")

    def build_chunk_metadata(
        self, chunk: DocumentChunk, document: Document
    ) -> dict[str, Any]:
        """Build metadata dict for a chunk stored in the vector DB.

        Extracted images are referenced (id + display info, not bytes) so
        search results can surface and serve them to the user.

        The result is capped to stay under Milvus's JSON field max length
        (65536). Document-level ``additional_info`` (e.g. marker's
        ``page_stats`` for EVERY page) is trimmed to only the chunk's own
        page, so a large PDF doesn't embed a multi-hundred-KB blob into each
        row (which previously failed with:
        ``MilvusException: the length (108621) of json field (metadata)
        exceeds max length (65536)``).
        """
        image_meta: list[dict[str, Any]] = []
        for img in chunk.images:
            description = (img.description or "").strip()
            if len(description) > _MAX_METADATA_STRING_LENGTH:
                description = description[:_MAX_METADATA_STRING_LENGTH] + "..."
            image_meta.append(
                {
                    "image_id": img.image_id,
                    "page_num": img.page_num,
                    "mime_type": img.mime_type,
                    "width": img.width,
                    "height": img.height,
                    "description": description,
                }
            )

        doc_meta = document.metadata.model_dump()
        doc_meta["additional_info"] = _chunk_additional_info(
            doc_meta.get("additional_info"), chunk.page_num
        )

        meta = {
            "page_num": chunk.page_num,
            "chunk_num": chunk.chunk_num,
            "has_images": bool(chunk.images),
            "image_count": len(chunk.images),
            "images": image_meta,
            **doc_meta,
        }
        return _cap_metadata_size(meta)

    @staticmethod
    def sanitize_id(document_id: str) -> str:
        """Sanitize document_id to prevent filter injection."""
        return document_id.replace('"', "").replace("\\", "")

    @staticmethod
    def group_documents(results: list[dict[str, Any]]) -> list[DocumentInfo]:
        """Group query results by parent_doc_id into DocumentInfo list."""
        doc_map: dict[str, dict[str, Any]] = {}
        for item in results:
            doc_id = item.get("parent_doc_id")
            metadata = item.get("metadata", {})
            if doc_id and doc_id not in doc_map:
                doc_map[doc_id] = {
                    "document_id": doc_id,
                    "filename": metadata.get("filename"),
                    "filesize": metadata.get("filesize"),
                    "filetype": metadata.get("filetype"),
                    "additional_info": {
                        "source_path": metadata.get("source_path", ""),
                        "content_hash": metadata.get("content_hash", ""),
                        **(metadata.get("additional_info") or {}),
                    },
                    "chunk_count": 0,
                }
            if doc_id:
                doc_map[doc_id]["chunk_count"] += 1
        return [
            DocumentInfo(
                document_id=d["document_id"],
                filename=d.get("filename"),
                filesize=d.get("filesize"),
                filetype=d.get("filetype"),
                chunk_count=d["chunk_count"],
                additional_info=d.get("additional_info"),
            )
            for d in doc_map.values()
        ]
