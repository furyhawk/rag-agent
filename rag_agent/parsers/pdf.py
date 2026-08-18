"""Smart PDF parser using marker (datalab-to/marker): PDF → markdown.

Marker converts PDFs to clean markdown while handling layout analysis,
table reconstruction, header/footer removal, image extraction and (optionally)
OCR internally. This parser adapts marker's paginated markdown output back into
the per-page ``DocumentPage`` model the rest of the pipeline expects.

Notes
-----
- Requires ``pip install marker-pdf`` and its inference prerequisites
  (PyTorch; a surya VLM backend is only needed when OCR is enabled).
- Models are downloaded on first use via ``create_model_dict()``.
- With ``enable_ocr=False`` (default) marker runs pure text-layer extraction
  (``disable_ocr=True``) — no VLM/inference server is started.
- Marker downloads ``GoNotoCurrent-Regular.ttf`` from ``models.datalab.to`` on
  first use. We vendor a copy in ``./fonts`` and point ``FONT_PATH`` at it so
  PDF parsing works in offline/air-gapped containers (see
  ``rag_agent/parsers/fonts/README.md``).
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any

from rag_agent.models.document import Document, DocumentImage, DocumentPage
from rag_agent.parsers.base import BaseDocumentParser

logger = logging.getLogger(__name__)

# ── Offline font for marker ─────────────────────────────────────────────
# marker's BaseConverter.__init__ calls marker.util.download_font() whenever
# settings.FONT_PATH is missing, which downloads GoNotoCurrent-Regular.ttf from
# models.datalab.to. In containers with egress/DNS blocked that download fails
# and every PDF conversion aborts. The env var must be set *before* marker's
# settings module is imported (marker's Settings is a pydantic BaseSettings and
# reads FONT_PATH from the environment). We only set it when the vendored font
# is actually present so we fall back to marker's normal behaviour otherwise.
_FONT_FILE = Path(__file__).resolve().parent / "fonts" / "GoNotoCurrent-Regular.ttf"
if _FONT_FILE.exists():
    os.environ.setdefault("FONT_PATH", str(_FONT_FILE))

# Marker's paginate_output inserts "\n\n{PAGE_ID}" + "-"*48 + "\n\n" between pages.
_PAGE_SEPARATOR = re.compile(r"\n\n\{(\d+)\}-{40,}\n\n")
# Markdown image reference, e.g. ![](/page/0/Picture/2.png)
_IMAGE_REF = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")

# marker's model dict is expensive to build; build once per process.
_model_dict: dict[str, Any] | None = None
_model_dict_lock = threading.Lock()


def _get_model_dict() -> dict[str, Any]:
    """Return the shared marker model dict (lazily built, thread-safe)."""
    global _model_dict
    if _model_dict is None:
        with _model_dict_lock:
            if _model_dict is None:
                from marker.models import create_model_dict

                _model_dict = create_model_dict()
    return _model_dict


class MarkerPDFParser(BaseDocumentParser):
    """PDF parser backed by datalab-to/marker (PDF → markdown).

    Marker performs layout analysis, table formatting, header/footer
    stripping, image extraction and (optionally) OCR internally, so this
    parser is thin: it runs the converter and splits the paginated markdown
    back into per-page ``DocumentPage`` objects.
    """

    SUPPORTED_EXTENSIONS = {".pdf"}

    def __init__(
        self,
        enable_ocr: bool = False,
        image_describer: Any = None,
    ) -> None:
        self.enable_ocr = enable_ocr
        self._image_describer = image_describer

    def _build_converter(self) -> Any:
        """Create a marker PdfConverter (models are shared process-wide)."""
        from marker.converters.pdf import PdfConverter

        config: dict[str, Any] = {
            "output_format": "markdown",
            "paginate_output": True,  # emit per-page separators we split on
            "disable_ocr": not self.enable_ocr,
            "extract_images": True,
            "disable_tqdm": True,
            "pdftext_workers": 1,
        }
        return PdfConverter(
            artifact_dict=_get_model_dict(),
            config=config,
        )

    @staticmethod
    def _split_pages(markdown: str) -> list[tuple[int, str]]:
        """Split paginated markdown into (1-based page_num, content) pairs."""
        parts = _PAGE_SEPARATOR.split(markdown)
        sections: list[tuple[int, str]] = []
        # parts[0] is any text before the first page marker (usually empty).
        for i in range(1, len(parts), 2):
            page_id = int(parts[i])
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            sections.append((page_id + 1, content))
        return sections

    @staticmethod
    def _pil_to_document_image(image: Any, page_num: int) -> DocumentImage:
        """Serialize a marker PIL image into a DocumentImage."""
        buffer = io.BytesIO()
        fmt = (image.format or "PNG").upper()
        if fmt in ("JPEG", "JPG"):
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(buffer, format="JPEG")
            mime_type = "image/jpeg"
        else:
            image.save(buffer, format="PNG")
            mime_type = "image/png"
        width, height = image.size
        return DocumentImage(
            page_num=page_num,
            image_bytes=buffer.getvalue(),
            mime_type=mime_type,
            width=width,
            height=height,
        )

    def _attach_page_images(
        self,
        content: str,
        images: dict[str, Any],
        page_num: int,
    ) -> tuple[list[DocumentImage], str]:
        """Pull images referenced by a page's markdown out of marker's dict.

        Returns ``(page_images, cleaned_content)``. Image markdown references
        are stripped from the content (images are stored/described separately,
        matching the pre-marker behavior).
        """
        page_images: list[DocumentImage] = []

        def _replace(match: re.Match) -> str:
            name = match.group(1)
            image = images.get(name)
            if image is not None:
                page_images.append(
                    self._pil_to_document_image(image, page_num)
                )
            return ""

        cleaned = _IMAGE_REF.sub(_replace, content)
        return page_images, cleaned

    @staticmethod
    def _toc_item(item: Any) -> dict[str, Any]:
        """Normalize a marker TocItem (pydantic model or dict) to a dict."""
        if isinstance(item, dict):
            return {
                "level": item.get("heading_level"),
                "title": item.get("title"),
                "page": (item.get("page_id") or 0) + 1,
            }
        return {
            "level": getattr(item, "heading_level", None),
            "title": getattr(item, "title", None),
            "page": (getattr(item, "page_id", 0) or 0) + 1,
        }

    def _parse_pdf_file(self, filepath: Path) -> Document:
        """Parse PDF with marker's converter."""
        from marker.output import text_from_rendered

        converter = self._build_converter()
        rendered = converter(str(filepath))
        markdown, _, images = text_from_rendered(rendered)
        metadata = getattr(rendered, "metadata", None) or {}

        sections = self._split_pages(markdown)
        if not sections and markdown.strip():
            # No page separators found — treat the whole output as one page.
            sections = [(1, markdown.strip())]

        pages: list[DocumentPage] = []
        for page_num, content in sections:
            page_images, cleaned = self._attach_page_images(
                content, images, page_num
            )
            pages.append(
                DocumentPage(
                    page_num=page_num,
                    content=cleaned,
                    images=page_images,
                )
            )

        # Enrich metadata from marker's output metadata.
        additional: dict[str, Any] = {}
        toc = metadata.get("table_of_contents")
        if toc:
            # Marker emits TocItem pydantic models; normalize to dicts.
            additional["toc"] = [self._toc_item(t) for t in toc[:20]]
        page_stats = metadata.get("page_stats")
        if page_stats:
            additional["page_stats"] = [
                s.model_dump(mode="json")
                if hasattr(s, "model_dump")
                else s
                for s in page_stats
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
                f"Extension {filepath.suffix} not supported by MarkerPDFParser"
            )
        # Marker conversion is CPU/GPU bound and blocking; run it in a worker
        # thread so we don't stall the event loop.
        return await asyncio.to_thread(self._parse_pdf_file, filepath)
