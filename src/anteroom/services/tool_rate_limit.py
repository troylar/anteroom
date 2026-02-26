"""Tool call rate limiting: per-minute, per-conversation, and consecutive-failure caps."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolRateLimitConfig:
    """Configuration for tool call rate limiting.

    All limits default to 0 (unlimited). Set a positive value to enable.
    """

    max_calls_per_minute: int = 0
    max_calls_per_conversation: int = 0
    max_consecutive_failures: int = 5
    action: str = "block"  # "block" | "warn"


@dataclass
class RateLimitVerdict:
    """Returned when a rate limit is exceeded."""

    exceeded: bool = False
    reason: str = ""
    limit_type: str = ""  # "per_minute" | "per_conversation" | "consecutive_failures"


class ToolRateLimiter:
    """Tracks tool call rates and enforces configurable limits.

    Instantiated per-request (web UI) or per-session (CLI). Shared across
    parent and child subagents so all tool calls count toward the same limits.
    """

    def __init__(self, config: ToolRateLimitConfig | None = None) -> None:
        self._config = config or ToolRateLimitConfig()
        self._call_timestamps: deque[float] = deque()
        self._total_calls: int = 0
        self._consecutive_failures: int = 0

    @property
    def config(self) -> ToolRateLimitConfig:
        return self._config

    @property
    def total_calls(self) -> int:
        return self._total_calls

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    def check(self, tool_name: str = "") -> RateLimitVerdict | None:
        """Check whether the next tool call should be allowed.

        Returns a RateLimitVerdict if a limit is exceeded, or None if allowed.
        """
        cfg = self._config

        # Per-minute sliding window
        if cfg.max_calls_per_minute > 0:
            now = time.monotonic()
            cutoff = now - 60.0
            while self._call_timestamps and self._call_timestamps[0] < cutoff:
                self._call_timestamps.popleft()
            if len(self._call_timestamps) >= cfg.max_calls_per_minute:
                return RateLimitVerdict(
                    exceeded=True,
                    reason=f"Tool call rate limit exceeded: {cfg.max_calls_per_minute} calls/minute",
                    limit_type="per_minute",
                )

        # Per-conversation total
        if cfg.max_calls_per_conversation > 0:
            if self._total_calls >= cfg.max_calls_per_conversation:
                return RateLimitVerdict(
                    exceeded=True,
                    reason=f"Tool call limit exceeded: {cfg.max_calls_per_conversation} calls/conversation",
                    limit_type="per_conversation",
                )

        # Consecutive failures
        if cfg.max_consecutive_failures > 0:
            if self._consecutive_failures >= cfg.max_consecutive_failures:
                return RateLimitVerdict(
                    exceeded=True,
                    reason=f"Too many consecutive tool failures: {self._consecutive_failures}",
                    limit_type="consecutive_failures",
                )

        return None

    def record_call(self, *, success: bool = True) -> None:
        """Record a tool call after execution."""
        self._total_calls += 1
        self._call_timestamps.append(time.monotonic())

        if success:
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1

    def reset(self) -> None:
        """Reset all counters for a new conversation."""
        self._call_timestamps.clear()
        self._total_calls = 0
        self._consecutive_failures = 0

    def reset_failures(self) -> None:
        """Reset only the consecutive failure counter."""
        self._consecutive_failures = 0
