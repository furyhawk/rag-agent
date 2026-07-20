"""OpenAI-compatible embedding provider.

Works with any OpenAI-compatible endpoint: OpenAI, Ollama, vLLM, TEI, etc.
"""

from __future__ import annotations

import logging

from openai import OpenAI

from rag_agent.embeddings.base import BaseEmbeddingProvider
from rag_agent.models.document import Document

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI-compatible embedding provider."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model
        resolved_key = api_key or "no-key-required"
        resolved_url = base_url or "https://api.openai.com/v1"
        self.client = OpenAI(base_url=resolved_url, api_key=resolved_key)

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of query texts."""
        response = self.client.embeddings.create(
            model=self.model, input=texts
        )
        return [data.embedding for data in response.data]

    def embed_document(self, document: Document) -> list[list[float]]:
        """Embed all chunks of a document."""
        texts = [
            chunk.chunk_content
            for chunk in (document.chunks or [])
        ]
        logger.info(
            "embedding.document",
            filename=document.metadata.filename,
            chunks=len(texts),
            model=self.model,
        )
        return self.embed_queries(texts)
