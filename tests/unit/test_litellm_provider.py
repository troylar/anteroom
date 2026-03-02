"""Tests for LiteLLMService provider."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from anteroom.config import AIConfig

# Inject a mock litellm module before importing litellm_provider,
# so that the try/except import succeeds and `litellm` is bound as a module attribute.
_mock_litellm_module = MagicMock()
sys.modules.setdefault("litellm", _mock_litellm_module)

from anteroom.services.litellm_provider import LiteLLMService  # noqa: E402


def _make_config(**overrides: object) -> AIConfig:
    defaults: dict[str, object] = {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "sk-or-test-key",
        "model": "openrouter/openai/gpt-4o",
        "provider": "litellm",
        "request_timeout": 120,
        "retry_max_attempts": 0,
    }
    defaults.update(overrides)
    return AIConfig(**defaults)


class _AsyncChunkIterator:
    """Helper that creates a proper async iterator from a list of chunks."""

    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = list(chunks)
        self._index = 0

    def __aiter__(self) -> "_AsyncChunkIterator":
        return self

    async def __anext__(self) -> Any:
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


def _make_service(config: AIConfig | None = None) -> LiteLLMService:
    """Build a LiteLLMService bypassing __init__."""
    svc = LiteLLMService.__new__(LiteLLMService)
    svc.config = config or _make_config()
    svc._token_provider = None
    return svc


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestLiteLLMServiceConstruction:
    def test_raises_without_litellm(self) -> None:
        with patch("anteroom.services.litellm_provider.HAS_LITELLM", False):
            with pytest.raises(ImportError, match="litellm"):
                LiteLLMService(_make_config())

    def test_constructs_with_litellm(self) -> None:
        with patch("anteroom.services.litellm_provider.HAS_LITELLM", True):
            svc = LiteLLMService(_make_config())
            assert svc.config.provider == "litellm"


# ---------------------------------------------------------------------------
# Factory routing
# ---------------------------------------------------------------------------


class TestCreateAiServiceFactoryLiteLLM:
    def test_litellm_provider_selected(self) -> None:
        with patch("anteroom.services.litellm_provider.HAS_LITELLM", True):
            from anteroom.services.ai_service import create_ai_service

            config = _make_config(provider="litellm")
            svc = create_ai_service(config)
            assert isinstance(svc, LiteLLMService)

    def test_openai_still_default(self) -> None:
        from anteroom.services.ai_service import AIService, create_ai_service

        config = _make_config(provider="openai", base_url="http://localhost:11434/v1")
        with patch("anteroom.services.ai_service.AsyncOpenAI"):
            svc = create_ai_service(config)
        assert isinstance(svc, AIService)


# ---------------------------------------------------------------------------
# _build_kwargs
# ---------------------------------------------------------------------------


class TestBuildKwargs:
    def test_basic_kwargs(self) -> None:
        svc = _make_service()
        kwargs = svc._build_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs["model"] == "openrouter/openai/gpt-4o"
        assert kwargs["api_key"] == "sk-or-test-key"
        assert kwargs["stream"] is False

    def test_stream_kwargs(self) -> None:
        svc = _make_service()
        kwargs = svc._build_kwargs([{"role": "user", "content": "hi"}], stream=True)
        assert kwargs["stream"] is True
        assert kwargs["stream_options"] == {"include_usage": True}

    def test_openrouter_headers_injected(self) -> None:
        svc = _make_service()
        kwargs = svc._build_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs["extra_headers"]["HTTP-Referer"] == "https://anteroom.ai"
        assert kwargs["extra_headers"]["X-Title"] == "Anteroom"

    def test_no_openrouter_headers_for_other_models(self) -> None:
        svc = _make_service(_make_config(model="gpt-4o", base_url="https://api.openai.com/v1"))
        kwargs = svc._build_kwargs([{"role": "user", "content": "hi"}])
        assert "extra_headers" not in kwargs

    def test_tools_passed(self) -> None:
        svc = _make_service()
        tools = [{"type": "function", "function": {"name": "test"}}]
        kwargs = svc._build_kwargs([{"role": "user", "content": "hi"}], tools=tools)
        assert kwargs["tools"] == tools

    def test_temperature_passed(self) -> None:
        svc = _make_service(_make_config(temperature=0.5))
        kwargs = svc._build_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs["temperature"] == 0.5

    def test_base_url_as_api_base(self) -> None:
        svc = _make_service()
        kwargs = svc._build_kwargs([{"role": "user", "content": "hi"}])
        assert kwargs["api_base"] == "https://openrouter.ai/api/v1"


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


class TestLiteLLMStreamChat:
    @pytest.mark.asyncio
    async def test_stream_text_tokens(self) -> None:
        svc = _make_service()
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "Hello"
        chunk.choices[0].delta.tool_calls = None
        chunk.choices[0].finish_reason = None
        chunk.usage = None

        done_chunk = MagicMock()
        done_chunk.choices = [MagicMock()]
        done_chunk.choices[0].delta.content = None
        done_chunk.choices[0].delta.tool_calls = None
        done_chunk.choices[0].finish_reason = "stop"
        done_chunk.usage = None

        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(return_value=_AsyncChunkIterator([chunk, done_chunk]))

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            events: list[dict[str, Any]] = []
            async for event in svc.stream_chat([{"role": "user", "content": "hi"}]):
                events.append(event)

        event_types = [e["event"] for e in events]
        assert "token" in event_types
        assert "done" in event_types

    @pytest.mark.asyncio
    async def test_stream_tool_call(self) -> None:
        svc = _make_service()
        tool_chunk = MagicMock()
        tool_chunk.choices = [MagicMock()]
        tool_chunk.choices[0].delta.content = None
        tc = MagicMock()
        tc.index = 0
        tc.id = "call_123"
        tc.function.name = "read_file"
        tc.function.arguments = '{"path": "/tmp/f"}'
        tool_chunk.choices[0].delta.tool_calls = [tc]
        tool_chunk.choices[0].finish_reason = None
        tool_chunk.usage = None

        done_chunk = MagicMock()
        done_chunk.choices = [MagicMock()]
        done_chunk.choices[0].delta.content = None
        done_chunk.choices[0].delta.tool_calls = None
        done_chunk.choices[0].finish_reason = "tool_calls"
        done_chunk.usage = None

        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(return_value=_AsyncChunkIterator([tool_chunk, done_chunk]))

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            events: list[dict[str, Any]] = []
            async for event in svc.stream_chat([{"role": "user", "content": "read file"}]):
                events.append(event)

        tool_events = [e for e in events if e["event"] == "tool_call"]
        assert len(tool_events) >= 1
        assert tool_events[0]["data"]["function_name"] == "read_file"

    @pytest.mark.asyncio
    async def test_stream_with_usage(self) -> None:
        svc = _make_service()
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "Hi"
        chunk.choices[0].delta.tool_calls = None
        chunk.choices[0].finish_reason = None
        chunk.usage = None

        done_chunk = MagicMock()
        done_chunk.choices = [MagicMock()]
        done_chunk.choices[0].delta.content = None
        done_chunk.choices[0].delta.tool_calls = None
        done_chunk.choices[0].finish_reason = "stop"
        usage = MagicMock()
        usage.prompt_tokens = 10
        usage.completion_tokens = 5
        usage.total_tokens = 15
        done_chunk.usage = usage

        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(return_value=_AsyncChunkIterator([chunk, done_chunk]))

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            events: list[dict[str, Any]] = []
            async for event in svc.stream_chat([{"role": "user", "content": "hi"}]):
                events.append(event)

        usage_events = [e for e in events if e["event"] == "usage"]
        assert len(usage_events) == 1
        assert usage_events[0]["data"]["prompt_tokens"] == 10


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestLiteLLMStreamErrors:
    @pytest.mark.asyncio
    async def test_auth_error(self) -> None:
        svc = _make_service()
        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(side_effect=Exception("AuthenticationError: invalid api key"))

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            events: list[dict[str, Any]] = []
            async for event in svc.stream_chat([{"role": "user", "content": "hi"}]):
                events.append(event)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["code"] == "auth_failed"

    @pytest.mark.asyncio
    async def test_rate_limit_error(self) -> None:
        svc = _make_service()
        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(side_effect=Exception("Rate limit exceeded"))

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            events: list[dict[str, Any]] = []
            async for event in svc.stream_chat([{"role": "user", "content": "hi"}]):
                events.append(event)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["code"] == "rate_limit"

    @pytest.mark.asyncio
    async def test_context_length_error(self) -> None:
        svc = _make_service()
        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(side_effect=Exception("context length exceeded"))

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            events: list[dict[str, Any]] = []
            async for event in svc.stream_chat([{"role": "user", "content": "hi"}]):
                events.append(event)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["code"] == "context_length_exceeded"

    @pytest.mark.asyncio
    async def test_transient_error_retries(self) -> None:
        svc = _make_service(_make_config(retry_max_attempts=1))
        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(side_effect=Exception("Connection reset"))

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            events: list[dict[str, Any]] = []
            async for event in svc.stream_chat([{"role": "user", "content": "hi"}]):
                events.append(event)

        retry_events = [e for e in events if e["event"] == "retrying"]
        assert len(retry_events) >= 1
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["retryable"] is True


# ---------------------------------------------------------------------------
# Generate title
# ---------------------------------------------------------------------------


class TestLiteLLMGenerateTitle:
    @pytest.mark.asyncio
    async def test_returns_title(self) -> None:
        svc = _make_service()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "A good title"

        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            title = await svc.generate_title("hello")
        assert title == "A good title"

    @pytest.mark.asyncio
    async def test_returns_fallback_on_error(self) -> None:
        svc = _make_service()
        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(side_effect=Exception("API error"))

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            title = await svc.generate_title("hello")
        assert title == "New Conversation"


# ---------------------------------------------------------------------------
# Validate connection
# ---------------------------------------------------------------------------


class TestLiteLLMValidateConnection:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        svc = _make_service()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Hi"

        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            ok, msg, models = await svc.validate_connection()
        assert ok is True
        assert "openrouter/openai/gpt-4o" in models

    @pytest.mark.asyncio
    async def test_failure(self) -> None:
        svc = _make_service()
        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            ok, msg, models = await svc.validate_connection()
        assert ok is False
        assert models == []


# ---------------------------------------------------------------------------
# Complete
# ---------------------------------------------------------------------------


class TestLiteLLMComplete:
    @pytest.mark.asyncio
    async def test_returns_text(self) -> None:
        svc = _make_service()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "The answer is 42"

        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(return_value=mock_resp)

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            result = await svc.complete([{"role": "user", "content": "question"}])
        assert result == "The answer is 42"

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self) -> None:
        svc = _make_service()
        mock_litellm = MagicMock()
        mock_litellm.acompletion = AsyncMock(side_effect=Exception("fail"))

        with patch("anteroom.services.litellm_provider.litellm", mock_litellm):
            result = await svc.complete([{"role": "user", "content": "question"}])
        assert result is None


# ---------------------------------------------------------------------------
# Inheritance check — LiteLLMService has the AIService interface
# ---------------------------------------------------------------------------


class TestLiteLLMInterface:
    def test_instance_has_required_methods(self) -> None:
        svc = _make_service()
        assert hasattr(svc, "stream_chat")
        assert hasattr(svc, "generate_title")
        assert hasattr(svc, "complete")
        assert hasattr(svc, "validate_connection")
