"""LLM-based image description for RAG document processing.

Uses an OpenAI-compatible vision endpoint to describe images extracted
from documents. Descriptions are appended to page content before
chunking, making image content searchable via text embeddings.
"""

from __future__ import annotations

import base64
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

IMAGE_DESCRIPTION_PROMPT = (
    "Describe this image in detail. Focus on any text, data, charts, diagrams, "
    "or visual information that would be useful for document search and retrieval. "
    "Be concise but comprehensive."
)


class BaseImageDescriber(ABC):
    """Abstract base for LLM-based image description."""

    @abstractmethod
    async def describe(
        self, image_bytes: bytes, mime_type: str = "image/png"
    ) -> str:
        """Generate a text description of an image."""
        ...


def _b64_encode(image_bytes: bytes) -> str:
    """Base64-encode raw image bytes."""
    return base64.b64encode(image_bytes).decode("utf-8")


class OpenAICompatibleImageDescriber(BaseImageDescriber):
    """Image description using an OpenAI-compatible vision API."""

    def __init__(
        self,
        model_name: str,
        base_url: str,
        api_key: str = "",
    ) -> None:
        self.model_name = model_name
        self._base_url = base_url
        self._api_key = api_key or "no-key-required"

    async def describe(
        self, image_bytes: bytes, mime_type: str = "image/png"
    ) -> str:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
            )
            b64 = _b64_encode(image_bytes)
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": IMAGE_DESCRIPTION_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{b64}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("Image description failed: %s", e)
            return ""
