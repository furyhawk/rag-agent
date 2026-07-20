"""Document processor — orchestrates parsing and chunking.

Extracted and generalized from agent_alpha.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rag_agent.chunkers.base import BaseChunker
from rag_agent.chunkers.markdown import MarkdownChunker
from rag_agent.chunkers.recursive import RecursiveChunker
from rag_agent.core.config import RAGSettings
from rag_agent.core.logging import get_logger
from rag_agent.models.document import Document, DocumentChunk
from rag_agent.parsers.base import BaseDocumentParser
from rag_agent.parsers.docx import DocxDocumentParser
from rag_agent.parsers.pdf import PyMuPDFParser
from rag_agent.parsers.text import TextDocumentParser

logger = get_logger(__name__)


class DocumentProcessor:
    """Orchestrates the parse → describe images → chunk pipeline.

    Routes files to the appropriate parser, optionally describes
    images via LLM vision, then chunks pages using the configured strategy.
    """

    def __init__(
        self,
        settings: RAGSettings,
        image_describer: Any = None,
    ) -> None:
        self.settings = settings
        self._image_describer = image_describer

        # Parsers
        self._text_parser = TextDocumentParser()
        self._docx_parser = DocxDocumentParser()
        self._pdf_parser = PyMuPDFParser(
            enable_ocr=settings.enable_ocr,
            image_describer=image_describer,
        )

        # Chunker
        self._chunker = self._create_chunker(settings)

    @staticmethod
    def _create_chunker(settings: RAGSettings) -> BaseChunker:
        if settings.chunking_strategy == "markdown":
            return MarkdownChunker()
        return RecursiveChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def _get_parser(self, filepath: Path) -> BaseDocumentParser:
        ext = filepath.suffix.lower()
        if ext in (".txt", ".md"):
            return self._text_parser
        if ext == ".docx":
            return self._docx_parser
        if ext == ".pdf":
            return self._pdf_parser
        raise ValueError(f"Unsupported file type: {ext}")

    async def _describe_images(self, document: Document) -> None:
        """Generate text descriptions for all images in document pages."""
        if not self._image_describer:
            return
        for page in document.pages:
            if not page.images:
                continue
            for image in page.images:
                image.description = await self._image_describer.describe(
                    image.image_bytes, image.mime_type
                )
            descriptions = [
                f"[Image: {img.description}]"
                for img in page.images
                if img.description
            ]
            if descriptions:
                page.content = f"{page.content}\n\n" + "\n".join(descriptions)

    async def process_file(self, filepath: Path) -> Document:
        """Main entry point: filepath → Document with chunks.

        Args:
            filepath: Path to the file to process.

        Returns:
            Document with parsed pages and chunked content.

        Raises:
            ValueError: If the file type is not supported.
        """
        parser = self._get_parser(filepath)
        document = await parser.parse(filepath)

        logger.info(
            "processor.parsed",
            filename=filepath.name,
            pages=len(document.pages),
            images=sum(len(p.images) for p in document.pages),
        )

        # Describe images before chunking
        await self._describe_images(document)

        # Chunk all pages
        chunks: list[DocumentChunk] = []
        for page in document.pages:
            page_chunks = self._chunker.chunk_page(page, document.id)
            chunks.extend(page_chunks)

        document.chunks = chunks

        logger.info(
            "processor.chunked",
            filename=filepath.name,
            chunks=len(chunks),
            strategy=self.settings.chunking_strategy,
            chunk_size=self.settings.chunk_size,
            overlap=self.settings.chunk_overlap,
        )

        return document
