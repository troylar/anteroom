"""Tests for token budget enforcement (issue #446)."""

from __future__ import annotations

import sqlite3
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from anteroom.config import BudgetConfig, UsageConfig
from anteroom.services import storage
from anteroom.services.token_budget import (
    BudgetCheckResult,
    check_all_budgets,
    check_budget,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _TestDB:
    """Minimal wrapper around sqlite3.Connection matching ThreadSafeConnection interface."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
        return self._conn.execute(sql, parameters)

    def execute_fetchall(self, sql: str, parameters: tuple[Any, ...] = ()) -> list[Any]:
        return self._conn.execute(sql, parameters).fetchall()

    def execute_fetchone(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
        return self._conn.execute(sql, parameters).fetchone()

    def commit(self) -> None:
        self._conn.commit()


def _make_db() -> _TestDB:
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
    db: _TestDB,
    conversation_id: str = "conv-1",
    total_tokens: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    created_at: str | None = None,
) -> str:
    import uuid

    mid = str(uuid.uuid4())
    if created_at:
        db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, "
            "total_tokens, prompt_tokens, completion_tokens, created_at) "
            "VALUES (?, ?, 'assistant', 'test', ?, ?, ?, ?)",
            (mid, conversation_id, total_tokens, prompt_tokens, completion_tokens, created_at),
        )
    else:
        db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, total_tokens, prompt_tokens, completion_tokens) "
            "VALUES (?, ?, 'assistant', 'test', ?, ?, ?)",
            (mid, conversation_id, total_tokens, prompt_tokens, completion_tokens),
        )
    db.commit()
    return mid


# ---------------------------------------------------------------------------
# BudgetConfig dataclass
# ---------------------------------------------------------------------------


class TestBudgetConfig:
    def test_defaults(self) -> None:
        cfg = BudgetConfig()
        assert cfg.enabled is False
        assert cfg.max_tokens_per_request == 0
        assert cfg.max_tokens_per_conversation == 0
        assert cfg.max_tokens_per_day == 0
        assert cfg.warn_threshold_percent == 80
        assert cfg.action_on_exceed == "block"

    def test_usage_config_has_budgets(self) -> None:
        usage = UsageConfig()
        assert isinstance(usage.budgets, BudgetConfig)
        assert usage.budgets.enabled is False

    def test_custom_values(self) -> None:
        cfg = BudgetConfig(
            enabled=True,
            max_tokens_per_request=50_000,
            max_tokens_per_conversation=500_000,
            max_tokens_per_day=2_000_000,
            warn_threshold_percent=90,
            action_on_exceed="warn",
        )
        assert cfg.enabled is True
        assert cfg.max_tokens_per_request == 50_000
        assert cfg.action_on_exceed == "warn"


# ---------------------------------------------------------------------------
# check_budget() pure logic
# ---------------------------------------------------------------------------


class TestCheckBudget:
    def test_unlimited_always_ok(self) -> None:
        status = check_budget(999_999, 0, 80, "test")
        assert status.result == BudgetCheckResult.OK
        assert status.limit == 0

    def test_under_limit_ok(self) -> None:
        status = check_budget(100, 1000, 80, "test")
        assert status.result == BudgetCheckResult.OK

    def test_at_warning_threshold(self) -> None:
        status = check_budget(800, 1000, 80, "conversation")
        assert status.result == BudgetCheckResult.WARNING
        assert status.label == "conversation"
        assert status.percent == 80.0

    def test_above_warning_below_limit(self) -> None:
        status = check_budget(900, 1000, 80, "daily")
        assert status.result == BudgetCheckResult.WARNING

    def test_at_limit_exceeded(self) -> None:
        status = check_budget(1000, 1000, 80, "request")
        assert status.result == BudgetCheckResult.EXCEEDED

    def test_over_limit_exceeded(self) -> None:
        status = check_budget(1500, 1000, 80, "request")
        assert status.result == BudgetCheckResult.EXCEEDED
        assert status.used == 1500
        assert status.limit == 1000

    def test_zero_threshold_no_warning(self) -> None:
        status = check_budget(900, 1000, 0, "test")
        assert status.result == BudgetCheckResult.OK

    def test_percent_property(self) -> None:
        status = check_budget(500, 1000, 80, "test")
        assert status.percent == 50.0

    def test_percent_unlimited(self) -> None:
        status = check_budget(500, 0, 80, "test")
        assert status.percent == 0.0

    def test_exactly_one_below_warning(self) -> None:
        status = check_budget(799, 1000, 80, "test")
        assert status.result == BudgetCheckResult.OK


# ---------------------------------------------------------------------------
# check_all_budgets()
# ---------------------------------------------------------------------------


class TestCheckAllBudgets:
    def test_all_unlimited_returns_none(self) -> None:
        result = check_all_budgets(100, 200, 300, 0, 0, 0, 80)
        assert result is None

    def test_all_under_returns_none(self) -> None:
        result = check_all_budgets(100, 200, 300, 1000, 1000, 1000, 80)
        assert result is None

    def test_request_exceeded(self) -> None:
        result = check_all_budgets(1000, 200, 300, 500, 0, 0, 80)
        assert result is not None
        assert result.result == BudgetCheckResult.EXCEEDED
        assert result.label == "request"

    def test_conversation_exceeded(self) -> None:
        result = check_all_budgets(100, 600, 300, 0, 500, 0, 80)
        assert result is not None
        assert result.result == BudgetCheckResult.EXCEEDED
        assert result.label == "conversation"

    def test_daily_exceeded(self) -> None:
        result = check_all_budgets(100, 200, 600, 0, 0, 500, 80)
        assert result is not None
        assert result.result == BudgetCheckResult.EXCEEDED
        assert result.label == "daily"

    def test_exceeded_takes_priority_over_warning(self) -> None:
        # Request: exceeded. Conversation: warning.
        result = check_all_budgets(1000, 450, 300, 500, 500, 0, 80)
        assert result is not None
        assert result.result == BudgetCheckResult.EXCEEDED
        assert result.label == "request"

    def test_warning_returned_when_no_exceeded(self) -> None:
        result = check_all_budgets(100, 450, 300, 0, 500, 0, 80)
        assert result is not None
        assert result.result == BudgetCheckResult.WARNING
        assert result.label == "conversation"


# ---------------------------------------------------------------------------
# Storage queries
# ---------------------------------------------------------------------------


class TestStorageBudgetQueries:
    def test_conversation_token_total_empty(self) -> None:
        db = _make_db()
        total = storage.get_conversation_token_total(db, "conv-1")
        assert total == 0

    def test_conversation_token_total_sums(self) -> None:
        db = _make_db()
        _insert_message(db, conversation_id="conv-1", total_tokens=100)
        _insert_message(db, conversation_id="conv-1", total_tokens=200)
        _insert_message(db, conversation_id="conv-2", total_tokens=999)
        total = storage.get_conversation_token_total(db, "conv-1")
        assert total == 300

    def test_conversation_token_total_ignores_null(self) -> None:
        db = _make_db()
        _insert_message(db, conversation_id="conv-1", total_tokens=100)
        _insert_message(db, conversation_id="conv-1", total_tokens=None)
        total = storage.get_conversation_token_total(db, "conv-1")
        assert total == 100

    def test_daily_token_total_empty(self) -> None:
        db = _make_db()
        total = storage.get_daily_token_total(db)
        assert total == 0

    def test_daily_token_total_sums_today(self) -> None:
        db = _make_db()
        _insert_message(db, total_tokens=100)
        _insert_message(db, total_tokens=200)
        total = storage.get_daily_token_total(db)
        assert total == 300

    def test_daily_token_total_excludes_old_messages(self) -> None:
        db = _make_db()
        _insert_message(db, total_tokens=100)  # today
        _insert_message(db, total_tokens=999, created_at="2020-01-01 00:00:00")
        total = storage.get_daily_token_total(db)
        assert total == 100


# ---------------------------------------------------------------------------
# Agent loop integration
# ---------------------------------------------------------------------------


def _make_stream_events(
    content: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
    usage: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if content:
        events.append({"event": "token", "data": {"content": content}})
    for tc in tool_calls or []:
        events.append({"event": "tool_call", "data": tc})
    if usage:
        events.append({"event": "usage", "data": usage})
    events.append({"event": "done", "data": {}})
    return events


def _mock_ai_service(*rounds: list[dict[str, Any]]) -> MagicMock:
    service = MagicMock()
    call_count = 0

    async def _stream_chat(messages: Any, **kwargs: Any) -> Any:
        nonlocal call_count
        idx = min(call_count, len(rounds) - 1)
        call_count += 1
        for event in rounds[idx]:
            yield event

    service.stream_chat = _stream_chat
    service.config = MagicMock()
    service.config.model = "test-model"
    return service


async def _collect_events(gen: Any) -> list[Any]:
    events = []
    async for e in gen:
        events.append(e)
    return events


class TestAgentLoopBudgetEnforcement:
    @pytest.mark.asyncio
    async def test_budget_disabled_no_effect(self) -> None:
        from anteroom.services.agent_loop import run_agent_loop

        ai = _mock_ai_service(_make_stream_events("hello", usage={"total_tokens": 100}))
        cfg = BudgetConfig(enabled=False, max_tokens_per_request=10)

        events = await _collect_events(
            run_agent_loop(
                ai_service=ai,
                messages=[{"role": "user", "content": "test"}],
                tool_executor=AsyncMock(),
                tools_openai=None,
                budget_config=cfg,
                get_token_totals=AsyncMock(return_value=(0, 0)),
            )
        )
        kinds = [e.kind for e in events]
        assert "error" not in kinds
        assert "assistant_message" in kinds

    @pytest.mark.asyncio
    async def test_conversation_budget_exceeded_blocks(self) -> None:
        from anteroom.services.agent_loop import run_agent_loop

        ai = _mock_ai_service(_make_stream_events("hello"))
        cfg = BudgetConfig(enabled=True, max_tokens_per_conversation=1000, action_on_exceed="block")

        events = await _collect_events(
            run_agent_loop(
                ai_service=ai,
                messages=[{"role": "user", "content": "test"}],
                tool_executor=AsyncMock(),
                tools_openai=None,
                budget_config=cfg,
                get_token_totals=AsyncMock(return_value=(1500, 0)),
            )
        )
        error_events = [e for e in events if e.kind == "error"]
        assert len(error_events) == 1
        assert error_events[0].data["code"] == "budget_exceeded"
        assert "conversation" in error_events[0].data["message"]
        # No thinking or token events should appear
        assert all(e.kind == "error" for e in events)

    @pytest.mark.asyncio
    async def test_daily_budget_exceeded_blocks(self) -> None:
        from anteroom.services.agent_loop import run_agent_loop

        ai = _mock_ai_service(_make_stream_events("hello"))
        cfg = BudgetConfig(enabled=True, max_tokens_per_day=500, action_on_exceed="block")

        events = await _collect_events(
            run_agent_loop(
                ai_service=ai,
                messages=[{"role": "user", "content": "test"}],
                tool_executor=AsyncMock(),
                tools_openai=None,
                budget_config=cfg,
                get_token_totals=AsyncMock(return_value=(0, 600)),
            )
        )
        error_events = [e for e in events if e.kind == "error"]
        assert len(error_events) == 1
        assert "daily" in error_events[0].data["message"]

    @pytest.mark.asyncio
    async def test_budget_exceeded_warn_mode_continues(self) -> None:
        from anteroom.services.agent_loop import run_agent_loop

        ai = _mock_ai_service(_make_stream_events("hello", usage={"total_tokens": 100}))
        cfg = BudgetConfig(enabled=True, max_tokens_per_conversation=1000, action_on_exceed="warn")

        events = await _collect_events(
            run_agent_loop(
                ai_service=ai,
                messages=[{"role": "user", "content": "test"}],
                tool_executor=AsyncMock(),
                tools_openai=None,
                budget_config=cfg,
                get_token_totals=AsyncMock(return_value=(1500, 0)),
            )
        )
        kinds = [e.kind for e in events]
        assert "budget_warning" in kinds
        assert "assistant_message" in kinds  # continued despite exceeded

    @pytest.mark.asyncio
    async def test_warning_threshold_emits_warning(self) -> None:
        from anteroom.services.agent_loop import run_agent_loop

        ai = _mock_ai_service(_make_stream_events("hello", usage={"total_tokens": 100}))
        cfg = BudgetConfig(enabled=True, max_tokens_per_conversation=1000, warn_threshold_percent=80)

        events = await _collect_events(
            run_agent_loop(
                ai_service=ai,
                messages=[{"role": "user", "content": "test"}],
                tool_executor=AsyncMock(),
                tools_openai=None,
                budget_config=cfg,
                get_token_totals=AsyncMock(return_value=(850, 0)),
            )
        )
        warning_events = [e for e in events if e.kind == "budget_warning"]
        assert len(warning_events) == 1
        assert "Approaching" in warning_events[0].data["message"]
        assert warning_events[0].data["label"] == "conversation"

    @pytest.mark.asyncio
    async def test_no_get_token_totals_skips_check(self) -> None:
        from anteroom.services.agent_loop import run_agent_loop

        ai = _mock_ai_service(_make_stream_events("hello", usage={"total_tokens": 100}))
        cfg = BudgetConfig(enabled=True, max_tokens_per_conversation=10)

        events = await _collect_events(
            run_agent_loop(
                ai_service=ai,
                messages=[{"role": "user", "content": "test"}],
                tool_executor=AsyncMock(),
                tools_openai=None,
                budget_config=cfg,
                get_token_totals=None,
            )
        )
        kinds = [e.kind for e in events]
        assert "error" not in kinds
        assert "assistant_message" in kinds

    @pytest.mark.asyncio
    async def test_request_budget_accumulates_across_iterations(self) -> None:
        """Per-request budget tracks tokens within a single run_agent_loop call."""
        from anteroom.services.agent_loop import run_agent_loop

        tc = {
            "id": "tc1",
            "function_name": "test_tool",
            "arguments": "{}",
        }
        # Round 1: tool call + usage. Round 2: another tool call + usage. Round 3: done.
        round1 = _make_stream_events(tool_calls=[tc], usage={"total_tokens": 300})
        round2 = _make_stream_events(tool_calls=[tc], usage={"total_tokens": 300})
        round3 = _make_stream_events("done", usage={"total_tokens": 100})

        ai = _mock_ai_service(round1, round2, round3)
        cfg = BudgetConfig(
            enabled=True,
            max_tokens_per_request=500,
            action_on_exceed="block",
        )

        async def _tool_exec(name: str, args: str) -> dict[str, Any]:
            return {"result": "ok"}

        events = await _collect_events(
            run_agent_loop(
                ai_service=ai,
                messages=[{"role": "user", "content": "test"}],
                tool_executor=_tool_exec,
                tools_openai=[{"type": "function", "function": {"name": "test_tool", "parameters": {}}}],
                budget_config=cfg,
                get_token_totals=AsyncMock(return_value=(0, 0)),
            )
        )
        # After round1 (300 tokens) + round2 (300 tokens) = 600, exceeds 500 limit
        # The check happens before each API call, so after accumulating 600 from rounds 1+2,
        # the check before round 3 should block.
        error_events = [e for e in events if e.kind == "error"]
        assert len(error_events) == 1
        assert error_events[0].data["code"] == "budget_exceeded"
        assert "request" in error_events[0].data["message"]

    @pytest.mark.asyncio
    async def test_totals_callback_error_gracefully_continues(self) -> None:
        from anteroom.services.agent_loop import run_agent_loop

        ai = _mock_ai_service(_make_stream_events("hello", usage={"total_tokens": 100}))
        cfg = BudgetConfig(enabled=True, max_tokens_per_conversation=10)

        async def _broken_totals() -> tuple[int, int]:
            raise RuntimeError("DB error")

        events = await _collect_events(
            run_agent_loop(
                ai_service=ai,
                messages=[{"role": "user", "content": "test"}],
                tool_executor=AsyncMock(),
                tools_openai=None,
                budget_config=cfg,
                get_token_totals=_broken_totals,
            )
        )
        kinds = [e.kind for e in events]
        # Should not error out — gracefully continues with 0 totals
        assert "assistant_message" in kinds


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------


class TestBudgetConfigParsing:
    def test_load_budget_from_yaml(self, tmp_path: Any) -> None:
        import yaml

        from anteroom.config import load_config

        config_data = {
            "ai": {"base_url": "http://localhost:8000", "api_key": "test", "model": "test"},
            "app": {"data_dir": str(tmp_path / "data")},
            "cli": {
                "usage": {
                    "budgets": {
                        "enabled": True,
                        "max_tokens_per_request": 50_000,
                        "max_tokens_per_conversation": 500_000,
                        "max_tokens_per_day": 2_000_000,
                        "warn_threshold_percent": 90,
                        "action_on_exceed": "warn",
                    }
                }
            },
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config, _ = load_config(config_file)
        budgets = config.cli.usage.budgets
        assert budgets.enabled is True
        assert budgets.max_tokens_per_request == 50_000
        assert budgets.max_tokens_per_conversation == 500_000
        assert budgets.max_tokens_per_day == 2_000_000
        assert budgets.warn_threshold_percent == 90
        assert budgets.action_on_exceed == "warn"

    def test_budget_defaults_when_absent(self, tmp_path: Any) -> None:
        import yaml

        from anteroom.config import load_config

        config_data = {
            "ai": {"base_url": "http://localhost:8000", "api_key": "test", "model": "test"},
            "app": {"data_dir": str(tmp_path / "data")},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config, _ = load_config(config_file)
        budgets = config.cli.usage.budgets
        assert budgets.enabled is False
        assert budgets.max_tokens_per_request == 0
        assert budgets.action_on_exceed == "block"

    def test_invalid_action_defaults_to_block(self, tmp_path: Any) -> None:
        import yaml

        from anteroom.config import load_config

        config_data = {
            "ai": {"base_url": "http://localhost:8000", "api_key": "test", "model": "test"},
            "app": {"data_dir": str(tmp_path / "data")},
            "cli": {"usage": {"budgets": {"action_on_exceed": "invalid"}}},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        config, _ = load_config(config_file)
        assert config.cli.usage.budgets.action_on_exceed == "block"

    def test_env_var_override(self, tmp_path: Any, monkeypatch: Any) -> None:
        import yaml

        from anteroom.config import load_config

        config_data = {
            "ai": {"base_url": "http://localhost:8000", "api_key": "test", "model": "test"},
            "app": {"data_dir": str(tmp_path / "data")},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        monkeypatch.setenv("AI_CHAT_BUDGET_ENABLED", "true")
        monkeypatch.setenv("AI_CHAT_BUDGET_MAX_TOKENS_PER_DAY", "1000000")

        config, _ = load_config(config_file)
        assert config.cli.usage.budgets.enabled is True
        assert config.cli.usage.budgets.max_tokens_per_day == 1_000_000
