"""Tests for token usage tracking and cost estimation (issue #226)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from anteroom.config import UsageConfig
from anteroom.services import storage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _TestDB:
    """Minimal wrapper around sqlite3.Connection matching ThreadSafeConnection interface."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql, parameters=()):
        return self._conn.execute(sql, parameters)

    def execute_fetchall(self, sql, parameters=()):
        return self._conn.execute(sql, parameters).fetchall()

    def execute_fetchone(self, sql, parameters=()):
        return self._conn.execute(sql, parameters).fetchone()

    def commit(self):
        self._conn.commit()


def _make_db() -> _TestDB:
    """Create an in-memory DB with the messages table including usage columns."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT,
            role TEXT,
            content TEXT,
            position INTEGER DEFAULT 0,
            user_id TEXT,
            user_display_name TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            prompt_tokens INTEGER DEFAULT NULL,
            completion_tokens INTEGER DEFAULT NULL,
            total_tokens INTEGER DEFAULT NULL,
            model TEXT DEFAULT NULL
        )"""
    )
    return _TestDB(conn)


def _insert_message(
    db,
    conversation_id: str = "conv-1",
    role: str = "assistant",
    content: str = "hello",
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    model: str | None = None,
    created_at: str | None = None,
    msg_id: str | None = None,
) -> str:
    import uuid

    mid = msg_id or str(uuid.uuid4())
    ts = created_at or datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO messages "
        "(id, conversation_id, role, content, prompt_tokens, completion_tokens, "
        "total_tokens, model, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (mid, conversation_id, role, content, prompt_tokens, completion_tokens, total_tokens, model, ts),
    )
    db.commit()
    return mid


# ---------------------------------------------------------------------------
# UsageConfig tests
# ---------------------------------------------------------------------------


class TestUsageConfig:
    def test_defaults(self):
        cfg = UsageConfig()
        assert cfg.week_days == 7
        assert cfg.month_days == 30
        assert "gpt-4o" in cfg.model_costs
        assert cfg.model_costs["gpt-4o"]["input"] == 2.50
        assert cfg.model_costs["gpt-4o"]["output"] == 10.00

    def test_custom_values(self):
        cfg = UsageConfig(week_days=5, month_days=28)
        assert cfg.week_days == 5
        assert cfg.month_days == 28

    def test_model_costs_structure(self):
        cfg = UsageConfig()
        for model, costs in cfg.model_costs.items():
            assert "input" in costs, f"Missing input cost for {model}"
            assert "output" in costs, f"Missing output cost for {model}"
            assert costs["input"] >= 0
            assert costs["output"] >= 0


# ---------------------------------------------------------------------------
# storage.update_message_usage tests
# ---------------------------------------------------------------------------


class TestUpdateMessageUsage:
    def test_updates_usage_fields(self):
        db = _make_db()
        mid = _insert_message(db)
        storage.update_message_usage(db, mid, 100, 200, 300, "gpt-4o")
        row = db.execute_fetchone(
            "SELECT prompt_tokens, completion_tokens, total_tokens, model FROM messages WHERE id = ?", (mid,)
        )
        assert row[0] == 100
        assert row[1] == 200
        assert row[2] == 300
        assert row[3] == "gpt-4o"

    def test_updates_only_target_message(self):
        db = _make_db()
        mid1 = _insert_message(db, msg_id="msg-1")
        mid2 = _insert_message(db, msg_id="msg-2")
        storage.update_message_usage(db, mid1, 50, 75, 125, "gpt-4o-mini")
        row2 = db.execute_fetchone("SELECT prompt_tokens FROM messages WHERE id = ?", (mid2,))
        assert row2[0] is None

    def test_overwrites_existing_usage(self):
        db = _make_db()
        mid = _insert_message(db, prompt_tokens=10, completion_tokens=20, total_tokens=30, model="old-model")
        storage.update_message_usage(db, mid, 100, 200, 300, "new-model")
        row = db.execute_fetchone("SELECT prompt_tokens, model FROM messages WHERE id = ?", (mid,))
        assert row[0] == 100
        assert row[1] == "new-model"


# ---------------------------------------------------------------------------
# storage.get_usage_stats tests
# ---------------------------------------------------------------------------


class TestGetUsageStats:
    def test_empty_db(self):
        db = _make_db()
        stats = storage.get_usage_stats(db)
        assert stats == []

    def test_no_usage_data_messages(self):
        db = _make_db()
        _insert_message(db)  # no token data
        stats = storage.get_usage_stats(db)
        assert stats == []

    def test_aggregates_by_model(self):
        db = _make_db()
        _insert_message(db, prompt_tokens=100, completion_tokens=200, total_tokens=300, model="gpt-4o")
        _insert_message(db, prompt_tokens=50, completion_tokens=75, total_tokens=125, model="gpt-4o")
        _insert_message(db, prompt_tokens=10, completion_tokens=20, total_tokens=30, model="gpt-4o-mini")

        stats = storage.get_usage_stats(db)
        assert len(stats) == 2
        # Ordered by total_tokens DESC
        gpt4o = stats[0]
        assert gpt4o["model"] == "gpt-4o"
        assert gpt4o["prompt_tokens"] == 150
        assert gpt4o["completion_tokens"] == 275
        assert gpt4o["total_tokens"] == 425
        assert gpt4o["message_count"] == 2

        mini = stats[1]
        assert mini["model"] == "gpt-4o-mini"
        assert mini["total_tokens"] == 30

    def test_filters_by_since(self):
        db = _make_db()
        old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        recent_time = datetime.now(timezone.utc).isoformat()

        _insert_message(
            db, prompt_tokens=100, completion_tokens=200, total_tokens=300, model="gpt-4o", created_at=old_time
        )
        _insert_message(
            db, prompt_tokens=50, completion_tokens=75, total_tokens=125, model="gpt-4o", created_at=recent_time
        )

        since = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        stats = storage.get_usage_stats(db, since=since)
        assert len(stats) == 1
        assert stats[0]["total_tokens"] == 125

    def test_filters_by_conversation(self):
        db = _make_db()
        _insert_message(
            db, conversation_id="conv-a", prompt_tokens=100, completion_tokens=200, total_tokens=300, model="gpt-4o"
        )
        _insert_message(
            db, conversation_id="conv-b", prompt_tokens=50, completion_tokens=75, total_tokens=125, model="gpt-4o"
        )

        stats = storage.get_usage_stats(db, conversation_id="conv-a")
        assert len(stats) == 1
        assert stats[0]["total_tokens"] == 300

    def test_combined_filters(self):
        db = _make_db()
        old_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        recent_time = datetime.now(timezone.utc).isoformat()

        _insert_message(
            db,
            conversation_id="conv-a",
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            model="gpt-4o",
            created_at=old_time,
        )
        _insert_message(
            db,
            conversation_id="conv-a",
            prompt_tokens=50,
            completion_tokens=75,
            total_tokens=125,
            model="gpt-4o",
            created_at=recent_time,
        )
        _insert_message(
            db,
            conversation_id="conv-b",
            prompt_tokens=30,
            completion_tokens=40,
            total_tokens=70,
            model="gpt-4o",
            created_at=recent_time,
        )

        since = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        stats = storage.get_usage_stats(db, since=since, conversation_id="conv-a")
        assert len(stats) == 1
        assert stats[0]["total_tokens"] == 125


# ---------------------------------------------------------------------------
# Cost calculation tests
# ---------------------------------------------------------------------------


class TestCostCalculation:
    def test_known_model_cost(self):
        cfg = UsageConfig()
        # gpt-4o: input=$2.50/1M, output=$10.00/1M
        prompt_t = 1_000_000
        completion_t = 500_000
        cost = (prompt_t / 1_000_000) * cfg.model_costs["gpt-4o"]["input"] + (
            completion_t / 1_000_000
        ) * cfg.model_costs["gpt-4o"]["output"]
        assert cost == 2.50 + 5.00  # $7.50

    def test_unknown_model_zero_cost(self):
        cfg = UsageConfig()
        costs = cfg.model_costs.get("unknown-model-xyz", {})
        input_rate = costs.get("input", 0.0)
        output_rate = costs.get("output", 0.0)
        assert input_rate == 0.0
        assert output_rate == 0.0


# ---------------------------------------------------------------------------
# Agent loop usage event passthrough test
# ---------------------------------------------------------------------------


class TestAgentLoopUsageEvent:
    @pytest.mark.asyncio
    async def test_usage_event_yielded(self):
        """Verify that the agent loop forwards usage events from ai_service."""
        from anteroom.services.agent_loop import run_agent_loop

        usage_data = {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300, "model": "gpt-4o"}

        async def mock_stream_chat(messages, **kwargs):
            yield {"event": "token", "data": {"content": "hello"}}
            yield {"event": "usage", "data": usage_data}
            yield {"event": "done", "data": {}}

        ai_service = MagicMock()
        ai_service.stream_chat = mock_stream_chat
        ai_service.config.model = "gpt-4o"

        messages: list[dict] = [{"role": "user", "content": "test"}]
        events = []
        async for event in run_agent_loop(
            ai_service=ai_service,
            messages=messages,
            tool_executor=AsyncMock(),
            tools_openai=None,
        ):
            events.append(event)

        usage_events = [e for e in events if e.kind == "usage"]
        assert len(usage_events) == 1
        assert usage_events[0].data == usage_data


# ---------------------------------------------------------------------------
# AI service usage capture test
# ---------------------------------------------------------------------------


class TestAIServiceUsageCapture:
    @pytest.mark.asyncio
    async def test_stream_options_includes_usage(self):
        """Verify that stream_options includes include_usage: True."""
        from anteroom.config import AIConfig
        from anteroom.services.ai_service import AIService

        config = AIConfig(
            base_url="http://localhost:1234",
            api_key="test-key",
            model="test-model",
        )

        ai = AIService(config)

        # Mock the client to capture the kwargs
        captured_kwargs = {}

        class MockStream:
            def __init__(self):
                self._events = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

            async def close(self):
                pass

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return MockStream()

        ai.client.chat.completions.create = mock_create

        # Consume the stream
        try:
            async for _ in ai.stream_chat([{"role": "user", "content": "test"}]):
                pass
        except Exception:
            pass  # Expected — mock doesn't produce valid stream

        assert captured_kwargs.get("stream_options") == {"include_usage": True}
