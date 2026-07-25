"""Embedding providers for RAG agent."""

from rag_agent.embeddings.base import BaseEmbeddingProvider
from rag_agent.embeddings.local import LocalEmbeddingProvider
from rag_agent.embeddings.local_omni import LocalOmniEmbeddingProvider
from rag_agent.embeddings.openai_compat import OpenAIEmbeddingProvider

__all__ = [
    "BaseEmbeddingProvider",
    "LocalEmbeddingProvider",
    "LocalOmniEmbeddingProvider",
    "OpenAIEmbeddingProvider",
]
