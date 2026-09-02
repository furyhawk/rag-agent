from __future__ import annotations

import asyncio
import sys
import types

from rag_agent.models.search import SearchResult
from rag_agent.rerankers.base import CrossEncoderReranker


def _result(content: str) -> SearchResult:
    return SearchResult(content=content, score=0.0)


def test_cross_encoder_falls_back_to_cpu_on_triton_compiler_error(monkeypatch) -> None:
    created_devices: list[str | None] = []

    class FakeCrossEncoder:
        def __init__(self, model_name, device=None):
            self.model_name = model_name
            self.device = device
            created_devices.append(device)

        def predict(self, pairs):
            if self.device != "cpu":
                raise RuntimeError(
                    "Failed to find C compiler. Please specify via CC environment variable or set triton.knobs.build.impl."
                )
            # Return higher score for the second pair to verify ordering.
            return [0.3, 0.9]

    fake_module = types.SimpleNamespace(CrossEncoder=FakeCrossEncoder)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    reranker = CrossEncoderReranker(model_name="cross-encoder/ms-marco-MiniLM-L6-v2")
    results = asyncio.run(
        reranker.rerank(
            "query",
            [_result("first doc"), _result("second doc")],
            top_k=2,
        )
    )

    assert [r.content for r in results] == ["second doc", "first doc"]
    assert created_devices == [None, "cpu"]
