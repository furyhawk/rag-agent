"""Local omni embedding provider using jinaai/jina-embeddings-v5-omni-nano.

Supports both text and image embeddings in a shared latent space,
enabling cross-modal search (text queries matching image content).

Used when EMBEDDING_BASE_URL is empty and the model name contains "omni".
"""

from __future__ import annotations

import io
import os
from typing import Any

import numpy as np

from rag_agent.core.logging import get_logger
from rag_agent.embeddings.base import BaseEmbeddingProvider
from rag_agent.models.document import Document

logger = get_logger(__name__)


class LocalOmniEmbeddingProvider(BaseEmbeddingProvider):
    """Embedding provider using jinaai/jina-embeddings-v5-omni-nano.

    Encodes both text and images into a shared embedding space using
    sentence-transformers with the Jina v5 Omni model. For retrieval
    tasks, queries use a ``Query:`` prefix and documents use a
    ``Document:`` prefix. Chunks containing images produce a fused
    multimodal embedding (text + image averaged).
    """

    def __init__(
        self,
        model: str,
        cache_dir: str | None = None,
        default_task: str = "retrieval",
    ) -> None:
        self.model_name = model
        self._model: Any | None = None
        self.cache_dir = cache_dir
        self.default_task = default_task
        self._using_cpu_fallback = False

    @staticmethod
    def _is_triton_compiler_error(error: Exception) -> bool:
        msg = str(error)
        return (
            "Failed to find C compiler" in msg
            or "triton.knobs.build.impl" in msg
        )

    def _load_model(self, device: str | None = None) -> Any:
        try:
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Local omni embeddings require sentence-transformers and peft. "
                "Install with: pip install 'verity-rag[local-ml]'"
            ) from exc
        logger.info(
            "embedding.omni.load",
            model=self.model_name,
            task=self.default_task,
            device=device or "auto",
        )
        return SentenceTransformer(
            self.model_name,
            cache_folder=self.cache_dir,
            trust_remote_code=True,
            model_kwargs={"default_task": self.default_task},
            device=device,
        )

    # ── Model loading ────────────────────────────────────────────

    @property
    def model(self) -> Any:
        if self._model is None:
            preferred_device = os.getenv("EMBEDDING_DEVICE") or None
            self._model = self._load_model(device=preferred_device)
        return self._model

    def _with_triton_fallback(self, func: Any) -> Any:
        try:
            return func()
        except Exception as exc:
            if not self._using_cpu_fallback and self._is_triton_compiler_error(exc):
                logger.warning(
                    "embedding.omni.triton_fallback",
                    model=self.model_name,
                    error=str(exc),
                )
                self._using_cpu_fallback = True
                self._model = self._load_model(device="cpu")
                return func()
            raise

    # ── Image helpers ────────────────────────────────────────────

    @staticmethod
    def _bytes_to_pil(image_bytes: bytes) -> Any | None:
        """Convert raw image bytes to a PIL Image (RGB)."""
        try:
            from PIL import Image as PILImage

            img = PILImage.open(io.BytesIO(image_bytes))
            if img.mode != "RGB":
                img = img.convert("RGB")
            return img
        except Exception as exc:
            logger.warning("embedding.omni.image_decode_failed", error=str(exc))
            return None

    def _load_images(self, images: list[Any]) -> list[Any]:
        """Convert a list of DocumentImage objects to PIL Images."""
        pil_images: list[Any] = []
        for img_data in images:
            pil = self._bytes_to_pil(img_data.image_bytes)
            if pil is not None:
                pil_images.append(pil)
        return pil_images

    # ── Embedding API ────────────────────────────────────────────

    @staticmethod
    def _force_text_input(text: str) -> str:
        """Normalize URL-like strings so the omni model treats them as plain text.

        The upstream model inspects string inputs and may treat URL-prefixed
        strings as media sources (image/video/audio/pdf). Some document chunks
        begin with citation links and newline content, which can trigger URL
        parsing errors. Prefixing these inputs keeps them on the text path.
        """
        stripped = text.lstrip()
        if stripped.startswith(("http://", "https://", "file://", "data:")):
            return f"Text: {text}"
        return text

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of query texts with the ``Query:`` prefix.

        Batches text-only encoding for efficiency.
        """
        normalized_texts = [self._force_text_input(t) for t in texts]
        embeddings = self._with_triton_fallback(
            lambda: self.model.encode(
                normalized_texts,
                prompt_name="query",
                show_progress_bar=False,
            )
        )
        return (
            embeddings.tolist()
            if isinstance(embeddings, np.ndarray)
            else [e.tolist() for e in embeddings]
        )

    def embed_document(self, document: Document) -> list[list[float]]:
        """Embed all chunks of a document with optional image fusion.

        For chunks that contain extracted images, the provider loads
        the first image and fuses it with the chunk text into a single
        multimodal embedding via ``encode_document()``. Text-only
        chunks are encoded normally with the ``Document:`` prefix.
        """
        chunks = document.chunks or []
        logger.info(
            "embedding.omni.document",
            filename=document.metadata.filename,
            chunks=len(chunks),
            model=self.model_name,
        )

        vectors: list[list[float]] = []
        for chunk in chunks:
            chunk_text = self._force_text_input(chunk.chunk_content)
            if chunk.images:
                pil_images = self._load_images(chunk.images)
                if pil_images:
                    # Fused multimodal embedding: text + first image
                    emb = self._with_triton_fallback(
                        lambda: self.model.encode_document(
                            (chunk_text, pil_images[0])
                        )
                    )
                else:
                    emb = self._with_triton_fallback(
                        lambda: self.model.encode_document(chunk_text)
                    )
            else:
                emb = self._with_triton_fallback(
                    lambda: self.model.encode_document(chunk_text)
                )

            vectors.append(
                emb.tolist()
                if isinstance(emb, np.ndarray)
                else list(emb)
            )

        return vectors

    def warmup(self) -> None:
        """Preload the model into memory."""
        _ = self.model
