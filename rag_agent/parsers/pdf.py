"""Smart PDF parser using PyMuPDF.

Features:
- Text extraction with layout preservation (blocks)
- Table detection → markdown tables
- Header/footer detection and removal
- OCR fallback for scanned pages (optional, via LLM vision)
- Image extraction for LLM-based description
- Document metadata (author, title, TOC)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pymupdf

from rag_agent.models.document import Document, DocumentImage, DocumentPage
from rag_agent.parsers.base import BaseDocumentParser

logger = logging.getLogger(__name__)


class PyMuPDFParser(BaseDocumentParser):
    """Smart PDF parser with multi-stage extraction pipeline."""

    SUPPORTED_EXTENSIONS = {".pdf"}
    MIN_TEXT_LENGTH = 50  # below this → likely a scan, try OCR

    def __init__(
        self,
        enable_ocr: bool = False,
        image_describer: Any = None,
    ) -> None:
        self.enable_ocr = enable_ocr
        self._image_describer = image_describer

    def _detect_repeated_content(self, doc: Any) -> set[str]:
        """Detect headers/footers — text appearing on >70% of pages."""
        if len(doc) < 3:
            return set()
        text_counts: dict[str, int] = {}
        for page in doc:
            for b in page.get_text("blocks"):
                if b[6] != 0:  # skip image blocks
                    continue
                y_ratio = b[1] / page.rect.height if page.rect.height else 0
                if y_ratio < 0.15 or y_ratio > 0.85:
                    text = b[4].strip()
                    if text and len(text) < 200:
                        text_counts[text] = text_counts.get(text, 0) + 1
        threshold = len(doc) * 0.7
        return {t for t, c in text_counts.items() if c >= threshold}

    def _extract_text(self, page: Any, repeated: set[str]) -> str:
        """Extract text blocks, filtering headers/footers."""
        texts = []
        for b in page.get_text("blocks"):
            if b[6] != 0:  # skip image blocks
                continue
            text = b[4].strip()
            if text and text not in repeated:
                texts.append(text)
        return "\n\n".join(texts)

    def _extract_tables(self, page: Any) -> str:
        """Extract tables as markdown."""
        try:
            tables = page.find_tables()
            if not tables or not tables.tables:
                return ""
            parts = []
            for table in tables.tables:
                df = table.to_pandas()
                if not df.empty:
                    parts.append(df.to_markdown(index=False))
            return "\n\n".join(parts)
        except Exception:
            return ""

    def _ocr_page(self, page: Any) -> str:
        """OCR a scanned page by rendering it as image and sending to LLM vision."""
        if not self._image_describer:
            return ""
        try:
            import asyncio

            pix = page.get_pixmap(dpi=200)
            image_bytes = pix.tobytes("png")
            loop = asyncio.new_event_loop()
            try:
                return str(
                    loop.run_until_complete(
                        self._image_describer.describe(image_bytes, "image/png")
                    )
                )
            finally:
                loop.close()
        except Exception as e:
            logger.warning("LLM OCR failed for page %d: %s", page.number + 1, e)
            return ""

    def _extract_images(self, doc: Any, page: Any) -> list[DocumentImage]:
        """Extract images from page for LLM description."""
        images: list[DocumentImage] = []
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                base = doc.extract_image(xref)
                if base and base["image"] and len(base["image"]) > 1000:
                    ext = base.get("ext", "png")
                    mime_map = {
                        "png": "image/png",
                        "jpeg": "image/jpeg",
                        "jpg": "image/jpeg",
                    }
                    images.append(
                        DocumentImage(
                            page_num=page.number + 1,
                            image_bytes=base["image"],
                            mime_type=mime_map.get(ext, f"image/{ext}"),
                        )
                    )
            except Exception:
                pass
        return images

    def _parse_pdf_file(self, filepath: Path) -> Document:
        """Parse PDF with smart extraction pipeline."""
        doc: Any = pymupdf.open(filepath)

        # Doc-level metadata
        meta = doc.metadata or {}
        toc = doc.get_toc()

        # Detect repeated headers/footers
        repeated = self._detect_repeated_content(doc)

        pages: list[DocumentPage] = []
        for page in doc:
            # 1. Text with layout (skip image blocks, filter headers/footers)
            text = self._extract_text(page, repeated)

            # 2. Tables → markdown
            tables_md = self._extract_tables(page)
            if tables_md:
                text = text + "\n\n" + tables_md if text.strip() else tables_md

            # 3. OCR fallback for scans/empty pages
            if self.enable_ocr and len(text.strip()) < self.MIN_TEXT_LENGTH:
                ocr_text = self._ocr_page(page)
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
                    logger.info("OCR fallback used for page %d", page.number + 1)

            # 4. Images
            images = self._extract_images(doc, page)

            pages.append(
                DocumentPage(
                    page_num=page.number + 1,
                    content=text,
                    images=images,
                )
            )

        doc.close()

        # Enrich metadata
        additional: dict[str, Any] = {}
        if meta.get("title"):
            additional["pdf_title"] = meta["title"]
        if meta.get("author"):
            additional["pdf_author"] = meta["author"]
        if toc:
            additional["toc"] = [
                {"level": t[0], "title": t[1], "page": t[2]} for t in toc[:20]
            ]

        doc_meta = self.get_document_metadata(filepath)
        if additional:
            doc_meta.additional_info = {
                **(doc_meta.additional_info or {}),
                **additional,
            }

        return Document(pages=pages, metadata=doc_meta)

    async def parse(self, filepath: Path) -> Document:
        """Parse a PDF file.

        Raises:
            ValueError: If the file is not a PDF file.
        """
        if not self.is_extension_allowed(filepath):
            raise ValueError(
                f"Extension {filepath.suffix} not supported by PyMuPDFParser"
            )
        return self._parse_pdf_file(filepath)
