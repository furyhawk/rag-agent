"""Unit tests for chunk metadata size control (Milvus JSON field limit).

Regression tests for:

    MilvusException: (code=1100, message=the length (108621) of json field
    (metadata) exceeds max length (65536): invalid parameter[expected=valid
    length json string][actual=length exceeds max length])

marker puts a ``page_stats`` entry for EVERY page of the document into
``metadata.additional_info``. ``build_chunk_metadata`` used to copy that whole
document-level blob into every chunk's ``metadata`` JSON, so a large PDF blew
past Milvus's 65536-char JSON field limit. Now each chunk only carries its own
page's stats and the metadata is hard-capped under the limit.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from rag_agent.models.document import (
    Document,
    DocumentChunk,
    DocumentMetadata,
    DocumentPage,
)
from rag_agent.vectorstore.milvus import MilvusVectorStore

# Milvus JSON field max length reported in the error.
MILVUS_JSON_MAX = 65536


class _DummyEmbedder:
    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed_document(self, document) -> list[list[float]]:  # noqa: ARG002
        return [[0.1] * self.dim for _ in range(len(document.chunks or []))]


@pytest.fixture
def store() -> MilvusVectorStore:
    with patch(
        "rag_agent.vectorstore.milvus.AsyncMilvusClient",
        return_value=object(),
    ):
        return MilvusVectorStore(
            milvus_uri="http://localhost:19530",
            milvus_token="",
            embedding_dim=384,
            embedding_service=_DummyEmbedder(),
        )


def _page_stats_for(n_pages: int, block_meta_len: int = 500) -> list[dict]:
    """Build marker-style page_stats: one (large-ish) entry per page."""
    stats = []
    for page_id in range(n_pages):
        stats.append(
            {
                "page_id": page_id,
                "text_extraction_method": "pdftext",
                "block_counts": [["Text", 12], ["Title", 1]],
                "block_metadata": {"meta": "x" * block_meta_len},
            }
        )
    return stats


def _make_document(page_num: int, additional_info: dict | None) -> Document:
    return Document(
        pages=[DocumentPage(page_num=page_num, content="")],
        chunks=[
            DocumentChunk(
                chunk_id="c1",
                chunk_num=0,
                chunk_content="content",
                page_num=page_num,
                parent_doc_id="doc-1",
            )
        ],
        metadata=DocumentMetadata(
            filename="big.pdf",
            filesize=100 * 1024 * 1024,
            filetype="application/pdf",
            additional_info=additional_info,
        ),
    )


def _json_bytes(meta: dict) -> int:
    return len(json.dumps(meta, default=str, ensure_ascii=False).encode("utf-8"))


def test_huge_page_stats_stays_under_milvus_json_limit(store: MilvusVectorStore) -> None:
    """200-page page_stats would exceed 65536; fixed metadata must not."""
    additional = {
        "toc": [{"level": 1, "title": "Chapter", "page": i} for i in range(20)],
        # ~200 * ~580 bytes ≈ 116 KB of document-wide stats.
        "page_stats": _page_stats_for(200),
    }
    doc = _make_document(page_num=5, additional_info=additional)

    meta = store.build_chunk_metadata(doc.chunks[0], doc)

    assert _json_bytes(meta) < MILVUS_JSON_MAX
    # Only the chunk's own page stats are retained (page_id is 0-based).
    assert meta["additional_info"]["page_stats"]["page_id"] == 4


def test_page_stats_missing_page_falls_back_to_no_stats(store: MilvusVectorStore) -> None:
    """If the chunk's page isn't in page_stats, drop it rather than keep all."""
    additional = {"page_stats": _page_stats_for(3)}  # only 3 pages
    doc = _make_document(page_num=10, additional_info=additional)

    meta = store.build_chunk_metadata(doc.chunks[0], doc)

    assert "page_stats" not in meta["additional_info"]
    assert _json_bytes(meta) < MILVUS_JSON_MAX


def test_overlong_string_in_additional_info_is_truncated(store: MilvusVectorStore) -> None:
    """A giant string value gets truncated to keep the metadata under the cap."""
    additional = {"huge_blob": "y" * 200_000}
    doc = _make_document(page_num=1, additional_info=additional)

    meta = store.build_chunk_metadata(doc.chunks[0], doc)

    assert _json_bytes(meta) < MILVUS_JSON_MAX
    assert len(meta["additional_info"]["huge_blob"]) <= 503  # 500 + "..."
    assert meta["additional_info"]["huge_blob"].endswith("...")


def test_small_metadata_unchanged(store: MilvusVectorStore) -> None:
    """Ordinary metadata should not be truncated or modified."""
    additional = {"page_stats": _page_stats_for(1)}
    doc = _make_document(page_num=1, additional_info=additional)

    meta = store.build_chunk_metadata(doc.chunks[0], doc)

    assert meta["additional_info"]["page_stats"]["page_id"] == 0
    assert meta["additional_info"]["page_stats"]["block_metadata"]["meta"] == "x" * 500
    assert _json_bytes(meta) < MILVUS_JSON_MAX
