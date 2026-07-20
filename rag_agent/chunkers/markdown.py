"""Markdown header-based chunker using LangChain."""

from __future__ import annotations

from langchain_text_splitters import MarkdownHeaderTextSplitter

from rag_agent.chunkers.base import BaseChunker
from rag_agent.models.document import DocumentChunk, DocumentPage


class MarkdownChunker(BaseChunker):
    """Split text by markdown headers (#, ##, ###)."""

    def __init__(self) -> None:
        self._splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                ("###", "h3"),
            ],
            strip_headers=False,
        )

    def chunk_page(
        self, page: DocumentPage, parent_doc_id: str
    ) -> list[DocumentChunk]:
        md_docs = self._splitter.split_text(page.content)
        return [
            DocumentChunk(
                chunk_content=doc.page_content,
                chunk_num=i,
                page_num=page.page_num,
                page_id=page.page_id,
                parent_doc_id=parent_doc_id,
                images=page.images,
            )
            for i, doc in enumerate(md_docs)
        ]
