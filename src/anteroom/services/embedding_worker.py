"""Background worker for generating message embeddings."""

from __future__ import annotations

import asyncio
import hashlib
import logging

from . import storage
from .embeddings import EmbeddingService

logger = logging.getLogger(__name__)

MIN_CONTENT_LENGTH = 10


class EmbeddingWorker:
    def __init__(self, db: object, embedding_service: EmbeddingService, batch_size: int = 50) -> None:
        self._db = db
        self._service = embedding_service
        self._batch_size = batch_size
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def process_pending(self) -> int:
        """Process unembedded messages. Returns count of messages embedded."""
        messages = storage.get_unembedded_messages(self._db, limit=self._batch_size)
        if not messages:
            return 0

        # Filter out short messages
        eligible = [m for m in messages if len(m.get("content", "")) >= MIN_CONTENT_LENGTH]
        if not eligible:
            return 0

        texts = [m["content"] for m in eligible]
        embeddings = await self._service.embed_batch(texts, batch_size=self._batch_size)

        count = 0
        for msg, embedding in zip(eligible, embeddings):
            if embedding is None:
                continue
            content_hash = hashlib.sha256(msg["content"].encode()).hexdigest()
            try:
                storage.store_embedding(
                    self._db,
                    msg["id"],
                    msg["conversation_id"],
                    embedding,
                    content_hash,
                )
                count += 1
            except Exception as e:
                logger.error("Failed to store embedding for message %s: %s", msg["id"], type(e).__name__)

        if count:
            logger.info("Embedded %d messages", count)
        return count

    async def embed_message(self, message_id: str, content: str, conversation_id: str) -> None:
        """Embed a single message (called inline after message creation)."""
        if len(content) < MIN_CONTENT_LENGTH:
            return

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        embedding = await self._service.embed(content)
        if embedding is None:
            return

        try:
            storage.store_embedding(self._db, message_id, conversation_id, embedding, content_hash)
        except Exception as e:
            logger.error("Failed to store embedding for message %s: %s", message_id, type(e).__name__)

    async def run_forever(self, interval: float = 30.0) -> None:
        """Poll for unembedded messages at a regular interval."""
        self._running = True
        logger.info("Embedding worker started (interval=%.0fs)", interval)
        while self._running:
            try:
                await self.process_pending()
            except Exception as e:
                logger.error("Embedding worker error during processing: %s", type(e).__name__)
            await asyncio.sleep(interval)

    def start(self, interval: float = 30.0) -> None:
        """Start the background polling loop."""
        self._task = asyncio.ensure_future(self.run_forever(interval))

    def stop(self) -> None:
        """Stop the background polling loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
