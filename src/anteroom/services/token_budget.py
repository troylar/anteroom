"""Token budget enforcement for denial-of-wallet prevention.

Pure functions — no I/O, no side effects. Callers provide token counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BudgetCheckResult(str, Enum):
    """Result of a budget check."""

    OK = "ok"
    WARNING = "warning"
    EXCEEDED = "exceeded"


@dataclass(frozen=True)
class BudgetStatus:
    """Status of a budget check with details."""

    result: BudgetCheckResult
    used: int
    limit: int  # 0 = unlimited
    label: str  # "conversation", "daily", or "request"

    @property
    def percent(self) -> float:
        if self.limit <= 0:
            return 0.0
        return (self.used / self.limit) * 100.0


def check_budget(
    used: int,
    limit: int,
    warn_threshold_percent: int,
    label: str,
) -> BudgetStatus:
    """Check token usage against a budget limit.

    Args:
        used: Tokens consumed so far.
        limit: Maximum allowed tokens. 0 means unlimited.
        warn_threshold_percent: Percentage at which to warn (0-100).
        label: Human-readable label for the budget type.

    Returns:
        BudgetStatus with result, usage, and limit details.
    """
    if limit <= 0:
        return BudgetStatus(result=BudgetCheckResult.OK, used=used, limit=0, label=label)

    if used >= limit:
        return BudgetStatus(result=BudgetCheckResult.EXCEEDED, used=used, limit=limit, label=label)

    if warn_threshold_percent > 0 and used >= (limit * warn_threshold_percent / 100):
        return BudgetStatus(result=BudgetCheckResult.WARNING, used=used, limit=limit, label=label)

    return BudgetStatus(result=BudgetCheckResult.OK, used=used, limit=limit, label=label)


def check_all_budgets(
    request_tokens: int,
    conversation_tokens: int,
    daily_tokens: int,
    max_per_request: int,
    max_per_conversation: int,
    max_per_day: int,
    warn_threshold_percent: int,
) -> BudgetStatus | None:
    """Check all three budget types, returning the worst status or None if all OK.

    Returns the first EXCEEDED status, then the first WARNING, or None if all OK.
    Checks in order: request, conversation, daily.
    """
    checks = [
        check_budget(request_tokens, max_per_request, warn_threshold_percent, "request"),
        check_budget(conversation_tokens, max_per_conversation, warn_threshold_percent, "conversation"),
        check_budget(daily_tokens, max_per_day, warn_threshold_percent, "daily"),
    ]

    exceeded = [s for s in checks if s.result == BudgetCheckResult.EXCEEDED]
    if exceeded:
        return exceeded[0]

    warnings = [s for s in checks if s.result == BudgetCheckResult.WARNING]
    if warnings:
        return warnings[0]

    return None
