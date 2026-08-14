from __future__ import annotations

import sys
import types

import numpy as np

from rag_agent.embeddings.local import LocalEmbeddingProvider
from rag_agent.embeddings.local_omni import LocalOmniEmbeddingProvider


def test_local_embedding_falls_back_to_cpu_on_triton_compiler_error(monkeypatch) -> None:
    created_devices: list[str | None] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name, cache_folder=None, device=None):
            self.device = device
            created_devices.append(device)

        def encode(self, texts, show_progress_bar=False):
            if self.device != "cpu":
                raise RuntimeError(
                    "Failed to find C compiler. Please specify via CC environment variable or set triton.knobs.build.impl."
                )
            return np.array([[0.11, 0.22]])

    fake_module = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    provider = LocalEmbeddingProvider(model="all-MiniLM-L6-v2")
    vectors = provider.embed_queries(["hello"])

    assert vectors == [[0.11, 0.22]]
    assert created_devices == [None, "cpu"]


def test_local_omni_embedding_falls_back_to_cpu_on_triton_compiler_error(monkeypatch) -> None:
    created_devices: list[str | None] = []

    class FakeSentenceTransformer:
        def __init__(
            self,
            model_name,
            cache_folder=None,
            trust_remote_code=None,
            model_kwargs=None,
            device=None,
        ):
            self.device = device
            created_devices.append(device)

        def encode(self, texts, prompt_name=None, show_progress_bar=False):
            if self.device != "cpu":
                raise RuntimeError(
                    "Failed to find C compiler. Please specify via CC environment variable or set triton.knobs.build.impl."
                )
            return np.array([[0.33, 0.44]])

        def encode_document(self, text_or_pair):
            if self.device != "cpu":
                raise RuntimeError(
                    "Failed to find C compiler. Please specify via CC environment variable or set triton.knobs.build.impl."
                )
            return np.array([0.55, 0.66])

    fake_module = types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    provider = LocalOmniEmbeddingProvider(model="jinaai/jina-embeddings-v5-omni-nano")
    vectors = provider.embed_queries(["query text"])

    assert vectors == [[0.33, 0.44]]
    assert created_devices == [None, "cpu"]
