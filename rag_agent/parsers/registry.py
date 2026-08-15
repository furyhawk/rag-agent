"""Parser registry — maps file extensions to parser classes."""

from __future__ import annotations

from typing import Any

from rag_agent.parsers.base import BaseDocumentParser
from rag_agent.parsers.docx import DocxDocumentParser
from rag_agent.parsers.pdf import MarkerPDFParser
from rag_agent.parsers.text import TextDocumentParser

# All available parsers
_AVAILABLE_PARSERS: list[type[BaseDocumentParser]] = [
    TextDocumentParser,
    DocxDocumentParser,
    MarkerPDFParser,
]

# Extension → parser class mapping
PARSER_REGISTRY: dict[str, type[BaseDocumentParser]] = {}
for _parser_cls in _AVAILABLE_PARSERS:
    for _ext in _parser_cls.SUPPORTED_EXTENSIONS:
        PARSER_REGISTRY[_ext] = _parser_cls


def get_parser_for_extension(
    ext: str, **kwargs: Any
) -> BaseDocumentParser:
    """Get a parser instance for a file extension.

    Args:
        ext: File extension including the dot (e.g., ".pdf").
        **kwargs: Arguments forwarded to the parser constructor.

    Raises:
        ValueError: If no parser is registered for the extension.
    """
    ext = ext.lower()
    parser_cls = PARSER_REGISTRY.get(ext)
    if parser_cls is None:
        raise ValueError(
            f"No parser registered for extension '{ext}'. "
            f"Supported: {sorted(PARSER_REGISTRY.keys())}"
        )
    return parser_cls(**kwargs)


def get_supported_extensions() -> set[str]:
    """Return all supported file extensions."""
    return set(PARSER_REGISTRY.keys())
