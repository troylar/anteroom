"""Regression tests for agent loop conversation history management (#619).

The agent loop must append assistant responses to the messages list so
subsequent turns (including queued messages) see the complete context.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from anteroom.config import AIConfig
from anteroom.services.agent_loop import AgentEvent, run_agent_loop
from anteroom.services.ai_service import AIService


def _make_config(**overrides: Any) -> AIConfig:
    defaults = {
        "base_url": "http://localhost:11434/v1",
        "api_key": "test-key",
        "model": "gpt-4",
        "request_timeout": 120,
        "verify_ssl": True,
    }
    defaults.update(overrides)
    return AIConfig(**defaults)


def _make_ai_service() -> AIService:
    service = AIService.__new__(AIService)
    service.config = _make_config()
    service._token_provider = None
    service.client = MagicMock()
    return service


class TestAssistantResponseAppendedToHistory:
    """Regression: final assistant response must be in messages list.

    Before the fix, the no-tool-call path yielded assistant_message and done
    but never called messages.append(), so subsequent turns (queued or
    otherwise) missed the previous assistant response in conversation history.
    """

    @pytest.mark.asyncio
    async def test_final_response_appended_to_messages(self) -> None:
        """After a no-tool-call response, messages must contain the assistant reply."""
        ai_service = _make_ai_service()

        async def fake_stream_chat(messages: Any, **kwargs: Any):
            yield {"event": "token", "data": {"content": "The capital is Paris."}}
            yield {"event": "done", "data": {}}

        ai_service.stream_chat = fake_stream_chat

        messages: list[dict[str, Any]] = [{"role": "user", "content": "What is the capital of France?"}]

        events: list[AgentEvent] = []
        async for event in run_agent_loop(
            ai_service=ai_service,
            messages=messages,
            tool_executor=AsyncMock(),
            tools_openai=None,
        ):
            events.append(event)

        # The assistant response must now be in the messages list
        assert len(messages) == 2
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "The capital is Paris."

    @pytest.mark.asyncio
    async def test_empty_response_not_appended(self) -> None:
        """An empty assistant response should not be appended to messages."""
        ai_service = _make_ai_service()

        async def fake_stream_chat(messages: Any, **kwargs: Any):
            yield {"event": "done", "data": {}}

        ai_service.stream_chat = fake_stream_chat

        messages: list[dict[str, Any]] = [{"role": "user", "content": "hello"}]

        async for _ in run_agent_loop(
            ai_service=ai_service,
            messages=messages,
            tool_executor=AsyncMock(),
            tools_openai=None,
        ):
            pass

        # Only the original user message should remain
        assert len(messages) == 1

    @pytest.mark.asyncio
    async def test_multi_token_response_concatenated_and_appended(self) -> None:
        """Multiple token events must be concatenated into a single assistant message."""
        ai_service = _make_ai_service()

        async def fake_stream_chat(messages: Any, **kwargs: Any):
            yield {"event": "token", "data": {"content": "Hello "}}
            yield {"event": "token", "data": {"content": "world"}}
            yield {"event": "token", "data": {"content": "!"}}
            yield {"event": "done", "data": {}}

        ai_service.stream_chat = fake_stream_chat

        messages: list[dict[str, Any]] = [{"role": "user", "content": "greet me"}]

        async for _ in run_agent_loop(
            ai_service=ai_service,
            messages=messages,
            tool_executor=AsyncMock(),
            tools_openai=None,
        ):
            pass

        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Hello world!"
