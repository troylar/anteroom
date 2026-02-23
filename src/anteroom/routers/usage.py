"""Usage statistics API endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query, Request

from ..services import storage

router = APIRouter(tags=["usage"])


@router.get("/usage")
async def get_usage(
    request: Request,
    period: str | None = Query(None, pattern="^(day|week|month|all)$"),
    conversation_id: str | None = Query(
        None, pattern="^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    ),
) -> dict[str, Any]:
    """Get token usage statistics, optionally filtered by period and conversation."""
    config = request.app.state.config
    db = request.app.state.db
    usage_cfg = config.cli.usage
    now = datetime.now(timezone.utc)

    if period:
        periods_map: dict[str, tuple[str, str | None]] = {
            "day": ("Today", (now - timedelta(days=1)).isoformat()),
            "week": ("This week", (now - timedelta(days=usage_cfg.week_days)).isoformat()),
            "month": ("This month", (now - timedelta(days=usage_cfg.month_days)).isoformat()),
            "all": ("All time", None),
        }
        selected = [periods_map[period]]
    else:
        selected = [
            ("Today", (now - timedelta(days=1)).isoformat()),
            ("This week", (now - timedelta(days=usage_cfg.week_days)).isoformat()),
            ("This month", (now - timedelta(days=usage_cfg.month_days)).isoformat()),
            ("All time", None),
        ]

    results: dict[str, Any] = {}
    for label, since in selected:
        stats = storage.get_usage_stats(db, since=since, conversation_id=conversation_id)
        total_prompt = sum(s.get("prompt_tokens", 0) or 0 for s in stats)
        total_completion = sum(s.get("completion_tokens", 0) or 0 for s in stats)
        total_tokens = sum(s.get("total_tokens", 0) or 0 for s in stats)
        total_messages = sum(s.get("message_count", 0) or 0 for s in stats)

        total_cost = 0.0
        for s in stats:
            model = s.get("model", "") or ""
            prompt_t = s.get("prompt_tokens", 0) or 0
            completion_t = s.get("completion_tokens", 0) or 0
            costs = usage_cfg.model_costs.get(model, {})
            input_rate = costs.get("input", 0.0)
            output_rate = costs.get("output", 0.0)
            total_cost += (prompt_t / 1_000_000) * input_rate + (completion_t / 1_000_000) * output_rate

        results[label] = {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "message_count": total_messages,
            "estimated_cost": round(total_cost, 4),
            "by_model": [
                {
                    "model": s.get("model", "unknown"),
                    "prompt_tokens": s.get("prompt_tokens", 0) or 0,
                    "completion_tokens": s.get("completion_tokens", 0) or 0,
                    "total_tokens": s.get("total_tokens", 0) or 0,
                    "message_count": s.get("message_count", 0) or 0,
                }
                for s in stats
            ],
        }

    return results
