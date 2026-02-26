"""Tests for tool call rate limiting."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from anteroom.services.tool_rate_limit import (
    RateLimitVerdict,
    ToolRateLimitConfig,
    ToolRateLimiter,
)

# ── Config defaults ──────────────────────────────────────────────────────────


class TestToolRateLimitConfig:
    def test_defaults(self) -> None:
        cfg = ToolRateLimitConfig()
        assert cfg.max_calls_per_minute == 0
        assert cfg.max_calls_per_conversation == 0
        assert cfg.max_consecutive_failures == 5
        assert cfg.action == "block"

    def test_custom_values(self) -> None:
        cfg = ToolRateLimitConfig(
            max_calls_per_minute=30,
            max_calls_per_conversation=100,
            max_consecutive_failures=3,
            action="warn",
        )
        assert cfg.max_calls_per_minute == 30
        assert cfg.max_calls_per_conversation == 100
        assert cfg.max_consecutive_failures == 3
        assert cfg.action == "warn"


# ── Verdict dataclass ────────────────────────────────────────────────────────


class TestRateLimitVerdict:
    def test_defaults(self) -> None:
        v = RateLimitVerdict()
        assert v.exceeded is False
        assert v.reason == ""
        assert v.limit_type == ""

    def test_exceeded(self) -> None:
        v = RateLimitVerdict(exceeded=True, reason="too fast", limit_type="per_minute")
        assert v.exceeded is True
        assert v.reason == "too fast"
        assert v.limit_type == "per_minute"


# ── Limiter: basic lifecycle ─────────────────────────────────────────────────


class TestToolRateLimiterBasic:
    def test_default_config_when_none(self) -> None:
        limiter = ToolRateLimiter(None)
        assert limiter.config.max_calls_per_minute == 0

    def test_properties(self) -> None:
        limiter = ToolRateLimiter()
        assert limiter.total_calls == 0
        assert limiter.consecutive_failures == 0

    def test_record_call_increments_total(self) -> None:
        limiter = ToolRateLimiter()
        limiter.record_call(success=True)
        limiter.record_call(success=True)
        assert limiter.total_calls == 2

    def test_record_call_tracks_failures(self) -> None:
        limiter = ToolRateLimiter()
        limiter.record_call(success=False)
        limiter.record_call(success=False)
        assert limiter.consecutive_failures == 2

    def test_success_resets_failures(self) -> None:
        limiter = ToolRateLimiter()
        limiter.record_call(success=False)
        limiter.record_call(success=False)
        limiter.record_call(success=True)
        assert limiter.consecutive_failures == 0

    def test_reset_clears_all(self) -> None:
        limiter = ToolRateLimiter()
        limiter.record_call(success=False)
        limiter.record_call(success=False)
        limiter.record_call(success=True)
        limiter.reset()
        assert limiter.total_calls == 0
        assert limiter.consecutive_failures == 0

    def test_reset_failures_only(self) -> None:
        limiter = ToolRateLimiter()
        limiter.record_call(success=False)
        limiter.record_call(success=False)
        limiter.reset_failures()
        assert limiter.consecutive_failures == 0
        assert limiter.total_calls == 2


# ── check(): unlimited (0 = disabled) ───────────────────────────────────────


class TestCheckUnlimited:
    def test_all_zero_always_allows(self) -> None:
        limiter = ToolRateLimiter(ToolRateLimitConfig())
        for _ in range(100):
            limiter.record_call(success=True)
        assert limiter.check() is None

    def test_zero_per_minute_allows(self) -> None:
        cfg = ToolRateLimitConfig(max_calls_per_minute=0)
        limiter = ToolRateLimiter(cfg)
        for _ in range(50):
            limiter.record_call(success=True)
        assert limiter.check() is None

    def test_zero_per_conversation_allows(self) -> None:
        cfg = ToolRateLimitConfig(max_calls_per_conversation=0)
        limiter = ToolRateLimiter(cfg)
        for _ in range(50):
            limiter.record_call(success=True)
        assert limiter.check() is None

    def test_zero_consecutive_failures_allows(self) -> None:
        cfg = ToolRateLimitConfig(max_consecutive_failures=0)
        limiter = ToolRateLimiter(cfg)
        for _ in range(50):
            limiter.record_call(success=False)
        assert limiter.check() is None


# ── check(): per-minute ──────────────────────────────────────────────────────


class TestCheckPerMinute:
    def test_under_limit_allows(self) -> None:
        cfg = ToolRateLimitConfig(max_calls_per_minute=10)
        limiter = ToolRateLimiter(cfg)
        for _ in range(9):
            limiter.record_call(success=True)
        assert limiter.check() is None

    def test_at_limit_blocks(self) -> None:
        cfg = ToolRateLimitConfig(max_calls_per_minute=5)
        limiter = ToolRateLimiter(cfg)
        for _ in range(5):
            limiter.record_call(success=True)
        v = limiter.check()
        assert v is not None
        assert v.exceeded is True
        assert v.limit_type == "per_minute"
        assert "5 calls/minute" in v.reason

    def test_old_calls_expire(self) -> None:
        cfg = ToolRateLimitConfig(max_calls_per_minute=3)
        limiter = ToolRateLimiter(cfg)

        base = 1000.0
        with patch("anteroom.services.tool_rate_limit.time") as mock_time:
            mock_time.monotonic.return_value = base
            for _ in range(3):
                limiter.record_call(success=True)

            # At base, we're at the limit
            v = limiter.check()
            assert v is not None
            assert v.exceeded is True

            # 61 seconds later, old calls expired
            mock_time.monotonic.return_value = base + 61.0
            v = limiter.check()
            assert v is None

    def test_tool_name_in_check_does_not_affect_result(self) -> None:
        cfg = ToolRateLimitConfig(max_calls_per_minute=2)
        limiter = ToolRateLimiter(cfg)
        limiter.record_call(success=True)
        limiter.record_call(success=True)
        v = limiter.check("bash")
        assert v is not None
        assert v.exceeded is True


# ── check(): per-conversation ────────────────────────────────────────────────


class TestCheckPerConversation:
    def test_under_limit_allows(self) -> None:
        cfg = ToolRateLimitConfig(max_calls_per_conversation=50)
        limiter = ToolRateLimiter(cfg)
        for _ in range(49):
            limiter.record_call(success=True)
        assert limiter.check() is None

    def test_at_limit_blocks(self) -> None:
        cfg = ToolRateLimitConfig(max_calls_per_conversation=10)
        limiter = ToolRateLimiter(cfg)
        for _ in range(10):
            limiter.record_call(success=True)
        v = limiter.check()
        assert v is not None
        assert v.exceeded is True
        assert v.limit_type == "per_conversation"
        assert "10 calls/conversation" in v.reason

    def test_reset_allows_again(self) -> None:
        cfg = ToolRateLimitConfig(max_calls_per_conversation=5)
        limiter = ToolRateLimiter(cfg)
        for _ in range(5):
            limiter.record_call(success=True)
        assert limiter.check() is not None
        limiter.reset()
        assert limiter.check() is None


# ── check(): consecutive failures ────────────────────────────────────────────


class TestCheckConsecutiveFailures:
    def test_under_limit_allows(self) -> None:
        cfg = ToolRateLimitConfig(max_consecutive_failures=3)
        limiter = ToolRateLimiter(cfg)
        limiter.record_call(success=False)
        limiter.record_call(success=False)
        assert limiter.check() is None

    def test_at_limit_blocks(self) -> None:
        cfg = ToolRateLimitConfig(max_consecutive_failures=3)
        limiter = ToolRateLimiter(cfg)
        for _ in range(3):
            limiter.record_call(success=False)
        v = limiter.check()
        assert v is not None
        assert v.exceeded is True
        assert v.limit_type == "consecutive_failures"
        assert "3" in v.reason

    def test_success_resets_and_allows(self) -> None:
        cfg = ToolRateLimitConfig(max_consecutive_failures=3)
        limiter = ToolRateLimiter(cfg)
        limiter.record_call(success=False)
        limiter.record_call(success=False)
        limiter.record_call(success=True)
        limiter.record_call(success=False)
        limiter.record_call(success=False)
        assert limiter.check() is None

    def test_reset_failures_allows(self) -> None:
        cfg = ToolRateLimitConfig(max_consecutive_failures=2)
        limiter = ToolRateLimiter(cfg)
        limiter.record_call(success=False)
        limiter.record_call(success=False)
        assert limiter.check() is not None
        limiter.reset_failures()
        assert limiter.check() is None


# ── check(): priority order ──────────────────────────────────────────────────


class TestCheckPriority:
    def test_per_minute_checked_first(self) -> None:
        cfg = ToolRateLimitConfig(
            max_calls_per_minute=2,
            max_calls_per_conversation=2,
            max_consecutive_failures=2,
        )
        limiter = ToolRateLimiter(cfg)
        limiter.record_call(success=False)
        limiter.record_call(success=False)
        v = limiter.check()
        assert v is not None
        assert v.limit_type == "per_minute"

    def test_per_conversation_when_per_minute_ok(self) -> None:
        cfg = ToolRateLimitConfig(
            max_calls_per_minute=0,
            max_calls_per_conversation=2,
            max_consecutive_failures=0,
        )
        limiter = ToolRateLimiter(cfg)
        limiter.record_call(success=True)
        limiter.record_call(success=True)
        v = limiter.check()
        assert v is not None
        assert v.limit_type == "per_conversation"

    def test_consecutive_failures_when_others_ok(self) -> None:
        cfg = ToolRateLimitConfig(
            max_calls_per_minute=0,
            max_calls_per_conversation=0,
            max_consecutive_failures=2,
        )
        limiter = ToolRateLimiter(cfg)
        limiter.record_call(success=False)
        limiter.record_call(success=False)
        v = limiter.check()
        assert v is not None
        assert v.limit_type == "consecutive_failures"


# ── Integration with ToolRegistry ────────────────────────────────────────────


class TestRegistryIntegration:
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_in_call_tool(self) -> None:
        from anteroom.tools import ToolRegistry

        registry = ToolRegistry()

        async def dummy_handler(**kwargs: object) -> dict:
            return {"output": "ok"}

        registry.register(
            "dummy",
            dummy_handler,
            {"name": "dummy", "description": "test", "parameters": {}},
        )

        cfg = ToolRateLimitConfig(max_calls_per_conversation=2)
        limiter = ToolRateLimiter(cfg)
        registry.set_rate_limiter(limiter)

        r1 = await registry.call_tool("dummy", {})
        assert "error" not in r1

        r2 = await registry.call_tool("dummy", {})
        assert "error" not in r2

        r3 = await registry.call_tool("dummy", {})
        assert "error" in r3
        assert r3.get("rate_limited") is True

    @pytest.mark.asyncio
    async def test_rate_limiter_warn_mode_allows(self) -> None:
        from anteroom.tools import ToolRegistry

        registry = ToolRegistry()

        async def dummy_handler(**kwargs: object) -> dict:
            return {"output": "ok"}

        registry.register(
            "dummy",
            dummy_handler,
            {"name": "dummy", "description": "test", "parameters": {}},
        )

        cfg = ToolRateLimitConfig(max_calls_per_conversation=1, action="warn")
        limiter = ToolRateLimiter(cfg)
        registry.set_rate_limiter(limiter)

        r1 = await registry.call_tool("dummy", {})
        assert "error" not in r1

        r2 = await registry.call_tool("dummy", {})
        assert "error" not in r2

    @pytest.mark.asyncio
    async def test_rate_limiter_records_failures(self) -> None:
        from anteroom.tools import ToolRegistry

        registry = ToolRegistry()

        async def failing_handler(**kwargs: object) -> dict:
            return {"error": "something broke"}

        registry.register(
            "fail_tool",
            failing_handler,
            {"name": "fail_tool", "description": "test", "parameters": {}},
        )

        cfg = ToolRateLimitConfig(max_consecutive_failures=3)
        limiter = ToolRateLimiter(cfg)
        registry.set_rate_limiter(limiter)

        for _ in range(3):
            await registry.call_tool("fail_tool", {})

        r = await registry.call_tool("fail_tool", {})
        assert "error" in r
        assert r.get("rate_limited") is True

    @pytest.mark.asyncio
    async def test_no_limiter_always_allows(self) -> None:
        from anteroom.tools import ToolRegistry

        registry = ToolRegistry()

        async def dummy_handler(**kwargs: object) -> dict:
            return {"output": "ok"}

        registry.register(
            "dummy",
            dummy_handler,
            {"name": "dummy", "description": "test", "parameters": {}},
        )

        for _ in range(100):
            r = await registry.call_tool("dummy", {})
            assert "error" not in r


# ── Config parsing ───────────────────────────────────────────────────────────


class TestConfigParsing:
    def test_tool_rate_limit_in_safety_config(self) -> None:
        from anteroom.config import SafetyConfig

        sc = SafetyConfig()
        assert sc.tool_rate_limit is not None
        assert sc.tool_rate_limit.max_calls_per_minute == 0
        assert sc.tool_rate_limit.action == "block"

    def test_yaml_parsing_full(self, tmp_path: object) -> None:
        from pathlib import Path

        from anteroom.config import load_config

        p = Path(str(tmp_path)) / "config.yaml"
        p.write_text(
            "ai:\n"
            "  base_url: http://localhost\n"
            "  api_key: test-key\n"
            "safety:\n"
            "  tool_rate_limit:\n"
            "    max_calls_per_minute: 30\n"
            "    max_calls_per_conversation: 200\n"
            "    max_consecutive_failures: 10\n"
            "    action: warn\n"
        )
        cfg, _ = load_config(p)
        trl = cfg.safety.tool_rate_limit
        assert trl.max_calls_per_minute == 30
        assert trl.max_calls_per_conversation == 200
        assert trl.max_consecutive_failures == 10
        assert trl.action == "warn"

    def test_yaml_parsing_defaults(self, tmp_path: object) -> None:
        from pathlib import Path

        from anteroom.config import load_config

        p = Path(str(tmp_path)) / "config.yaml"
        p.write_text("ai:\n  base_url: http://localhost\n  api_key: test\n")
        cfg, _ = load_config(p)
        trl = cfg.safety.tool_rate_limit
        assert trl.max_calls_per_minute == 0
        assert trl.max_calls_per_conversation == 0
        assert trl.max_consecutive_failures == 5
        assert trl.action == "block"

    def test_invalid_action_falls_back(self, tmp_path: object) -> None:
        from pathlib import Path

        from anteroom.config import load_config

        p = Path(str(tmp_path)) / "config.yaml"
        p.write_text(
            "ai:\n  base_url: http://localhost\n  api_key: test\nsafety:\n  tool_rate_limit:\n    action: invalid\n"
        )
        cfg, _ = load_config(p)
        assert cfg.safety.tool_rate_limit.action == "block"

    def test_negative_values_clamped(self, tmp_path: object) -> None:
        from pathlib import Path

        from anteroom.config import load_config

        p = Path(str(tmp_path)) / "config.yaml"
        p.write_text(
            "ai:\n"
            "  base_url: http://localhost\n"
            "  api_key: test\n"
            "safety:\n"
            "  tool_rate_limit:\n"
            "    max_calls_per_minute: -5\n"
        )
        cfg, _ = load_config(p)
        assert cfg.safety.tool_rate_limit.max_calls_per_minute == 0


# ── Config validation ────────────────────────────────────────────────────────


class TestConfigValidation:
    def test_valid_config_no_errors(self) -> None:
        from anteroom.services.config_validator import validate_config

        raw = {
            "safety": {
                "tool_rate_limit": {
                    "max_calls_per_minute": 30,
                    "max_calls_per_conversation": 200,
                    "max_consecutive_failures": 10,
                    "action": "warn",
                },
            },
        }
        result = validate_config(raw)
        real_errors = [e for e in result.errors if e.severity == "error"]
        assert not real_errors

    def test_invalid_action_flagged(self) -> None:
        from anteroom.services.config_validator import validate_config

        raw = {
            "safety": {
                "tool_rate_limit": {"action": "explode"},
            },
        }
        result = validate_config(raw)
        has_enum_error = any("action" in str(e) and "explode" in str(e) for e in result.errors)
        assert has_enum_error

    def test_unknown_key_warned(self) -> None:
        from anteroom.services.config_validator import validate_config

        raw = {
            "safety": {
                "tool_rate_limit": {"unknown_field": 42},
            },
        }
        result = validate_config(raw)
        has_warning = any("unknown_field" in str(e) for e in result.errors if e.severity == "warning")
        assert has_warning

    def test_non_int_value_flagged(self) -> None:
        from anteroom.services.config_validator import validate_config

        raw = {
            "safety": {
                "tool_rate_limit": {"max_calls_per_minute": "fast"},
            },
        }
        result = validate_config(raw)
        has_error = any("max_calls_per_minute" in str(e) for e in result.errors)
        assert has_error
