"""SSE streaming for ingestion progress via Valkey pub/sub."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis
from sse_starlette.sse import ServerSentEvent

from rag_agent.core.config import Settings
from rag_agent.models.ingestion import IngestionProgress

logger = logging.getLogger(__name__)


class StatusService:
    """Publishes and streams ingestion progress events."""

    CHANNEL = "rag_status"

    def __init__(self, valkey: redis.Redis, settings: Settings) -> None:
        self._valkey = valkey
        self._settings = settings

    async def publish(self, progress: IngestionProgress) -> None:
        """Publish an ingestion progress event to Valkey pub/sub."""
        try:
            await self._valkey.publish(
                self.CHANNEL,
                json.dumps(progress.model_dump()),
            )
        except Exception as e:
            logger.warning("Status publish failed: %s", e)

    async def stream_events(self) -> Any:
        """Yield SSE events from Valkey pub/sub subscription."""
        pubsub = self._valkey.pubsub()
        await pubsub.subscribe(self.CHANNEL)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        event = ServerSentEvent(
                            data=data,
                            event="ingestion",
                        )
                        yield event
                    except Exception as e:
                        logger.warning("SSE parse failed: %s", e)
                elif message["type"] == "subscribe":
                    continue
        finally:
            await pubsub.unsubscribe(self.CHANNEL)
            await pubsub.close()
