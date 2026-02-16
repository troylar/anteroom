"""Tests for embedding service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anteroom.services.embeddings import EmbeddingService, create_embedding_service


def _make_embedding_response(embeddings: list[list[float]]) -> MagicMock:
    """Build a mock embeddings API response."""
    response = MagicMock()
    response.data = []
    for i, emb in enumerate(embeddings):
        item = MagicMock()
        item.index = i
        item.embedding = emb
        response.data.append(item)
    return response


class TestEmbeddingService:
    @pytest.mark.asyncio
    async def test_embed_calls_api(self) -> None:
        client = AsyncMock()
        client.embeddings.create = AsyncMock(return_value=_make_embedding_response([[0.1, 0.2, 0.3]]))
        service = EmbeddingService(client, model="test-model", dimensions=3)

        result = await service.embed("hello world")

        assert result == [0.1, 0.2, 0.3]
        client.embeddings.create.assert_called_once_with(
            model="test-model",
            input="hello world",
            dimensions=3,
        )

    @pytest.mark.asyncio
    async def test_embed_returns_none_on_empty_text(self) -> None:
        client = AsyncMock()
        service = EmbeddingService(client)

        assert await service.embed("") is None
        assert await service.embed("   ") is None
        client.embeddings.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_returns_none_on_error(self) -> None:
        client = AsyncMock()
        client.embeddings.create = AsyncMock(side_effect=Exception("API error"))
        service = EmbeddingService(client)

        result = await service.embed("hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_embed_batch(self) -> None:
        client = AsyncMock()
        client.embeddings.create = AsyncMock(return_value=_make_embedding_response([[0.1, 0.2], [0.3, 0.4]]))
        service = EmbeddingService(client, model="test-model", dimensions=2)

        results = await service.embed_batch(["hello", "world"], batch_size=10)

        assert len(results) == 2
        assert results[0] == [0.1, 0.2]
        assert results[1] == [0.3, 0.4]

    @pytest.mark.asyncio
    async def test_embed_batch_handles_error(self) -> None:
        client = AsyncMock()
        client.embeddings.create = AsyncMock(side_effect=Exception("API error"))
        service = EmbeddingService(client, dimensions=2)

        results = await service.embed_batch(["hello", "world"])
        assert results == [None, None]

    @pytest.mark.asyncio
    async def test_embed_batch_multiple_batches(self) -> None:
        client = AsyncMock()
        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            batch = kwargs["input"]
            resp = _make_embedding_response([[float(call_count)] for _ in batch])
            call_count += 1
            return resp

        client.embeddings.create = mock_create
        service = EmbeddingService(client, dimensions=1)

        results = await service.embed_batch(["a", "b", "c"], batch_size=2)
        assert len(results) == 3
        assert call_count == 2  # 2 batches: [a,b] and [c]

    def test_model_and_dimensions_properties(self) -> None:
        client = AsyncMock()
        service = EmbeddingService(client, model="custom-model", dimensions=768)
        assert service.model == "custom-model"
        assert service.dimensions == 768


class TestEmbeddingServiceTokenRefresh:
    @pytest.mark.asyncio
    async def test_embed_refreshes_token_on_auth_error(self) -> None:
        from openai import AuthenticationError

        client = AsyncMock()
        fresh_client = AsyncMock()
        fresh_client.embeddings.create = AsyncMock(return_value=_make_embedding_response([[0.1, 0.2]]))

        # First call raises auth error, second succeeds after refresh
        client.embeddings.create = AsyncMock(
            side_effect=AuthenticationError(message="invalid", response=MagicMock(status_code=401), body=None)
        )
        client.base_url = "https://api.test/v1"

        service = EmbeddingService(client, dimensions=2)

        # Set up a mock token provider
        provider = MagicMock()
        provider.refresh = MagicMock()
        provider.get_token = MagicMock(return_value="new-token")
        service._set_token_provider(provider)

        # Patch AsyncOpenAI to return fresh_client on re-creation
        with patch("anteroom.services.embeddings.AsyncOpenAI", return_value=fresh_client):
            result = await service.embed("hello world")

        assert result == [0.1, 0.2]
        provider.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_returns_none_when_refresh_fails(self) -> None:
        from openai import AuthenticationError

        from anteroom.services.token_provider import TokenProviderError

        client = AsyncMock()
        client.embeddings.create = AsyncMock(
            side_effect=AuthenticationError(message="invalid", response=MagicMock(status_code=401), body=None)
        )
        client.base_url = "https://api.test/v1"

        service = EmbeddingService(client, dimensions=2)

        provider = MagicMock()
        provider.refresh = MagicMock(side_effect=TokenProviderError("failed"))
        service._set_token_provider(provider)

        result = await service.embed("hello world")
        assert result is None

    @pytest.mark.asyncio
    async def test_embed_batch_refreshes_token_on_auth_error(self) -> None:
        from openai import AuthenticationError

        client = AsyncMock()
        fresh_client = AsyncMock()
        fresh_client.embeddings.create = AsyncMock(return_value=_make_embedding_response([[0.1], [0.2]]))

        client.embeddings.create = AsyncMock(
            side_effect=AuthenticationError(message="invalid", response=MagicMock(status_code=401), body=None)
        )
        client.base_url = "https://api.test/v1"

        service = EmbeddingService(client, dimensions=1)

        provider = MagicMock()
        provider.refresh = MagicMock()
        provider.get_token = MagicMock(return_value="new-token")
        service._set_token_provider(provider)

        with patch("anteroom.services.embeddings.AsyncOpenAI", return_value=fresh_client):
            results = await service.embed_batch(["hello", "world"])

        assert results == [[0.1], [0.2]]

    @pytest.mark.asyncio
    async def test_embed_truncates_long_text(self) -> None:
        from anteroom.services.embeddings import MAX_INPUT_TOKENS

        client = AsyncMock()
        client.embeddings.create = AsyncMock(return_value=_make_embedding_response([[0.1]]))
        service = EmbeddingService(client, dimensions=1)

        long_text = "a" * (MAX_INPUT_TOKENS * 4 + 1000)
        await service.embed(long_text)

        call_args = client.embeddings.create.call_args
        assert len(call_args.kwargs["input"]) == MAX_INPUT_TOKENS * 4


class TestCreateEmbeddingService:
    def test_returns_none_when_disabled(self) -> None:
        from anteroom.config import AIConfig, AppConfig, EmbeddingsConfig

        config = AppConfig(
            ai=AIConfig(base_url="https://api.test", api_key="sk-test"),
            embeddings=EmbeddingsConfig(enabled=False),
        )
        assert create_embedding_service(config) is None

    def test_returns_none_when_no_api_key(self) -> None:
        from anteroom.config import AIConfig, AppConfig, EmbeddingsConfig

        config = AppConfig(
            ai=AIConfig(base_url="https://api.test", api_key=""),
            embeddings=EmbeddingsConfig(enabled=True, api_key=""),
        )
        assert create_embedding_service(config) is None

    def test_creates_service_with_ai_config(self) -> None:
        from anteroom.config import AIConfig, AppConfig, EmbeddingsConfig

        config = AppConfig(
            ai=AIConfig(base_url="https://api.test", api_key="sk-test"),
            embeddings=EmbeddingsConfig(enabled=True),
        )
        service = create_embedding_service(config)
        assert service is not None
        assert service.model == "text-embedding-3-small"
        assert service.dimensions == 1536

    def test_creates_service_with_override_config(self) -> None:
        from anteroom.config import AIConfig, AppConfig, EmbeddingsConfig

        config = AppConfig(
            ai=AIConfig(base_url="https://api.test", api_key="sk-test"),
            embeddings=EmbeddingsConfig(
                enabled=True,
                base_url="https://embeddings.test",
                api_key="sk-embed",
                model="custom-embed",
                dimensions=768,
            ),
        )
        service = create_embedding_service(config)
        assert service is not None
        assert service.model == "custom-embed"
        assert service.dimensions == 768
