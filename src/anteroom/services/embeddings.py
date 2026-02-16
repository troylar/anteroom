"""Embedding service: generate vector embeddings via OpenAI-compatible API."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from openai import AsyncOpenAI, AuthenticationError

from ..config import AppConfig
from .token_provider import TokenProvider, TokenProviderError

logger = logging.getLogger(__name__)

MAX_INPUT_TOKENS = 8191


class EmbeddingService:
    def __init__(self, client: AsyncOpenAI, model: str = "text-embedding-3-small", dimensions: int = 1536) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions
        self._token_provider: TokenProvider | None = None

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _set_token_provider(self, provider: TokenProvider) -> None:
        self._token_provider = provider

    def _try_refresh_token(self) -> bool:
        if not self._token_provider:
            return False
        try:
            self._token_provider.refresh()
            new_key = self._token_provider.get_token()
            self._client = AsyncOpenAI(base_url=str(self._client.base_url), api_key=new_key)
            logger.info("Embedding service token refreshed")
            return True
        except TokenProviderError:
            logger.exception("Embedding token refresh failed")
            return False

    async def embed(self, text: str) -> list[float] | None:
        """Generate an embedding for a single text. Returns None on error."""
        if not text or not text.strip():
            return None
        truncated = text[: MAX_INPUT_TOKENS * 4]
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=truncated,
                dimensions=self._dimensions,
            )
            return response.data[0].embedding
        except AuthenticationError:
            if self._try_refresh_token():
                return await self.embed(text)
            logger.error("Embedding authentication failed")
            return None
        except Exception as e:
            logger.error("Failed to generate embedding: %s", type(e).__name__)
            return None

    async def embed_batch(self, texts: list[str], batch_size: int = 100) -> list[list[float] | None]:
        """Generate embeddings for a batch of texts."""
        results: list[list[float] | None] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            truncated = [t[: MAX_INPUT_TOKENS * 4] for t in batch]
            try:
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=truncated,
                    dimensions=self._dimensions,
                )
                batch_results: list[list[float] | None] = [None] * len(batch)
                for item in response.data:
                    batch_results[item.index] = item.embedding
                results.extend(batch_results)
            except AuthenticationError:
                if self._try_refresh_token():
                    retry_response = await self._client.embeddings.create(
                        model=self._model,
                        input=truncated,
                        dimensions=self._dimensions,
                    )
                    batch_results = [None] * len(batch)
                    for item in retry_response.data:
                        batch_results[item.index] = item.embedding
                    results.extend(batch_results)
                else:
                    logger.error("Embedding batch authentication failed")
                    results.extend([None] * len(batch))
            except Exception as e:
                logger.error("Failed to generate batch embeddings: %s", type(e).__name__)
                results.extend([None] * len(batch))
        return results


def create_embedding_service(config: AppConfig) -> EmbeddingService | None:
    """Factory: create an EmbeddingService from app config. Returns None if unavailable."""
    if not config.embeddings.enabled:
        return None

    base_url = config.embeddings.base_url or config.ai.base_url
    api_key = config.embeddings.api_key or config.ai.api_key
    api_key_command = config.embeddings.api_key_command or config.ai.api_key_command

    if not api_key and not api_key_command:
        return None

    provider: TokenProvider | None = None
    if api_key_command:
        provider = TokenProvider(api_key_command)
        api_key = provider.get_token()

    kwargs: dict[str, Any] = {
        "base_url": base_url,
        "api_key": api_key,
    }
    if not config.ai.verify_ssl:
        kwargs["http_client"] = httpx.AsyncClient(verify=False)  # noqa: S501

    client = AsyncOpenAI(**kwargs)
    service = EmbeddingService(
        client=client,
        model=config.embeddings.model,
        dimensions=config.embeddings.dimensions,
    )
    if provider:
        service._set_token_provider(provider)
    return service
