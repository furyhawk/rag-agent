"""Base embedding provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from rag_agent.models.document import Document


class BaseEmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of query texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors, one for each input text.
        """
        ...

    @abstractmethod
    def embed_document(self, document: Document) -> list[list[float]]:
        """Embed all chunks of a document.

        Args:
            document: Document object containing chunked pages.

        Returns:
            List of embedding vectors, one for each chunk.
        """
        ...

    def warmup(self) -> None:
        """Ensures the model is loaded and ready for inference."""
        pass
