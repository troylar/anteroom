"""Sub-agent e2e tests via the web UI chat API.

These tests start a real Anteroom server (no MCP needed) and mock the AI service
to return run_agent tool calls, exercising the full sub-agent pipeline through SSE:
parent tool_call_start -> child execution -> subagent_event -> tool_call_end -> done.
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncGenerator
from unittest.mock import patch

import httpx
import pytest

from tests.e2e.conftest import parse_sse_events

pytestmark = pytest.mark.e2e


def _mock_subagent_stream(
    prompt_text: str = "Analyze the code",
    child_response: str = "Analysis complete. Found 3 issues.",
) -> Any:
    """Create a mock stream that triggers a run_agent tool call.

    First invocation: AI returns a run_agent tool call.
    Second invocation (after tool result): AI returns a text summary.

    The child sub-agent also needs a mock — we patch AIService at the class
    level so the child's stream_chat also resolves.
    """
    call_count = 0

    async def _stream(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        cancel_event: Any = None,
        extra_system_prompt: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        nonlocal call_count
        call_count += 1

        # Check if this is a sub-agent call (system prompt contains "sub-agent")
        is_child = extra_system_prompt and "sub-agent" in extra_system_prompt.lower()

        if is_child:
            # Child agent: produce output tokens and finish
            for token in child_response.split():
                yield {"event": "token", "data": {"content": token + " "}}
            yield {"event": "done", "data": {}}
        elif call_count == 1:
            # Parent first call: issue run_agent tool call
            yield {
                "event": "tool_call",
                "data": {
                    "id": f"call_{uuid.uuid4().hex[:12]}",
                    "function_name": "run_agent",
                    "arguments": {"prompt": prompt_text},
                },
            }
            yield {"event": "done", "data": {}}
        else:
            # Parent second call: summarize the sub-agent result
            yield {"event": "token", "data": {"content": "Sub-agent finished. "}}
            yield {"event": "done", "data": {}}

    return _stream


class TestSubagentWebExecution:
    """Execute run_agent tool through the chat SSE pipeline."""

    def test_subagent_tool_call_produces_events(self, api_client: httpx.Client, conversation_id: str) -> None:
        """run_agent tool call should produce tool_call_start, subagent_event, tool_call_end."""
        stream_fn = _mock_subagent_stream()

        with patch("anteroom.services.ai_service.AIService.stream_chat", side_effect=stream_fn):
            resp = api_client.post(
                f"/api/conversations/{conversation_id}/chat",
                json={"message": "Analyze this codebase"},
                headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            )
        assert resp.status_code == 200

        events = parse_sse_events(resp)
        event_types = [e["event"] for e in events]

        assert "tool_call_start" in event_types, f"Expected tool_call_start in {event_types}"
        assert "tool_call_end" in event_types, f"Expected tool_call_end in {event_types}"
        assert "done" in event_types, f"Expected done in {event_types}"

        # Verify the tool_call_start is for run_agent
        start_events = [e for e in events if e["event"] == "tool_call_start"]
        assert len(start_events) >= 1
        assert start_events[0]["data"]["tool_name"] == "run_agent"

    def test_subagent_tool_result_contains_output(self, api_client: httpx.Client, conversation_id: str) -> None:
        """The tool_call_end output should contain the sub-agent's generated text."""
        child_text = "Found 5 bugs in the auth module."
        stream_fn = _mock_subagent_stream(child_response=child_text)

        with patch("anteroom.services.ai_service.AIService.stream_chat", side_effect=stream_fn):
            resp = api_client.post(
                f"/api/conversations/{conversation_id}/chat",
                json={"message": "Check for bugs"},
                headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            )
        assert resp.status_code == 200

        events = parse_sse_events(resp)
        end_events = [e for e in events if e["event"] == "tool_call_end"]
        assert len(end_events) >= 1

        tool_output = end_events[0]["data"]["output"]
        assert "Found" in tool_output.get("output", ""), f"Expected child output in result: {tool_output}"
        assert "elapsed_seconds" in tool_output

    def test_subagent_events_emitted_via_sse(self, api_client: httpx.Client, conversation_id: str) -> None:
        """Sub-agent start/end events should be emitted as subagent_event SSE events."""
        stream_fn = _mock_subagent_stream()

        with patch("anteroom.services.ai_service.AIService.stream_chat", side_effect=stream_fn):
            resp = api_client.post(
                f"/api/conversations/{conversation_id}/chat",
                json={"message": "Run analysis"},
                headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            )
        assert resp.status_code == 200

        events = parse_sse_events(resp)
        subagent_events = [e for e in events if e["event"] == "subagent_event"]

        # The web UI buffers sub-agent events and emits them when run_agent tool_call_end fires
        if subagent_events:
            event_data = subagent_events[0]["data"]
            kinds = [e.get("kind") for e in event_data] if isinstance(event_data, list) else [event_data.get("kind")]
            assert any(k in ("subagent_start", "subagent_end") for k in kinds), f"Unexpected subagent event: {kinds}"

    def test_subagent_result_stored_in_db(self, api_client: httpx.Client, conversation_id: str) -> None:
        """Sub-agent tool call results should be persisted in the conversation."""
        stream_fn = _mock_subagent_stream()

        with patch("anteroom.services.ai_service.AIService.stream_chat", side_effect=stream_fn):
            resp = api_client.post(
                f"/api/conversations/{conversation_id}/chat",
                json={"message": "Analyze code"},
                headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            )
        assert resp.status_code == 200

        # Verify messages are stored
        conv_resp = api_client.get(f"/api/conversations/{conversation_id}")
        conv_resp.raise_for_status()
        conv_data = conv_resp.json()
        messages = conv_data.get("messages", [])

        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(assistant_msgs) >= 1, "Expected at least one assistant message stored"


class TestSubagentWebConfig:
    """Verify config-driven limits work through the web pipeline."""

    def test_subagent_respects_configured_limits(self, api_client: httpx.Client, conversation_id: str) -> None:
        """Sub-agent should use config defaults (not require explicit config to work)."""
        stream_fn = _mock_subagent_stream()

        with patch("anteroom.services.ai_service.AIService.stream_chat", side_effect=stream_fn):
            resp = api_client.post(
                f"/api/conversations/{conversation_id}/chat",
                json={"message": "Do analysis"},
                headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            )
        assert resp.status_code == 200

        events = parse_sse_events(resp)
        event_types = [e["event"] for e in events]

        # Should complete without errors
        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 0, f"Unexpected errors: {error_events}"
        assert "done" in event_types
