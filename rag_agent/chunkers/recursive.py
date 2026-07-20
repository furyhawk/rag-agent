"""Recursive character text chunker using LangChain."""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_agent.chunkers.base import BaseChunker
from rag_agent.models.document import DocumentChunk, DocumentPage


class RecursiveChunker(BaseChunker):
    """Smart recursive splitting by paragraphs, sentences, words."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )

    def chunk_page(
        self, page: DocumentPage, parent_doc_id: str
    ) -> list[DocumentChunk]:
        texts = self._splitter.split_text(page.content)
        return [
            DocumentChunk(
                chunk_content=text,
                chunk_num=i,
                page_num=page.page_num,
                page_id=page.page_id,
                parent_doc_id=parent_doc_id,
                images=page.images,
            )
            for i, text in enumerate(texts)
        ]
