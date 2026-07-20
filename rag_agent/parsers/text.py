"""Parser for plain text and Markdown files."""

from __future__ import annotations

from pathlib import Path

from rag_agent.models.document import Document, DocumentPage
from rag_agent.parsers.base import BaseDocumentParser


class TextDocumentParser(BaseDocumentParser):
    """Parser for .txt and .md files using Python built-ins."""

    SUPPORTED_EXTENSIONS = {".txt", ".md"}

    async def parse(self, filepath: Path) -> Document:
        """Parse a text file.

        Raises:
            ValueError: If the file extension is not supported.
        """
        if not self.is_extension_allowed(filepath):
            raise ValueError(
                f"Extension {filepath.suffix} not supported by TextDocumentParser"
            )

        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        page = DocumentPage(page_num=1, content=content)
        return Document(pages=[page], metadata=self.get_document_metadata(filepath))
