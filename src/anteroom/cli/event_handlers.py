"""Agent loop event handlers for the CLI REPL."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from ..services import storage
from . import renderer
from .renderer import CHROME


@dataclass
class EventContext:
    """Mutable state passed through the event processing loop."""

    thinking: bool = False
    response_token_count: int = 0
    total_elapsed: float = 0.0
    should_retry: bool = False
    pending_usage: dict[str, Any] | None = None

    # Plan state references (from _agent_runner)
    plan_checklist_steps: list[str] = field(default_factory=list)
    plan_current_step: list[int] = field(default_factory=lambda: [0])
    plan_active: list[bool] = field(default_factory=lambda: [False])

    # Config
    max_retries: int = 3
    retry_delay: float = 2.0
    model_context_window: int = 128000
    auto_compact_threshold: int = 100000
    auto_plan_mode: str = "off"

    # References
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    user_attempt: int = 0
    db: Any = None
    conv_id: str = ""
    identity_kwargs: dict[str, str | None] = field(default_factory=dict)
    ai_messages: list[dict[str, Any]] = field(default_factory=list)

    # Callbacks
    apply_plan_mode: Any = None
    get_tiktoken_encoding: Any = None
    estimate_tokens: Any = None


async def handle_repl_event(ctx: EventContext, event: Any) -> None:
    """Process a single agent loop event, mutating ctx in place."""
    kind = event.kind

    if kind == "thinking":
        if not ctx.thinking:
            _advance_plan_step_complete(ctx)
            renderer.start_thinking(newline=True)
            ctx.thinking = True

    elif kind == "phase":
        renderer.set_thinking_phase(event.data.get("phase", ""))

    elif kind == "retrying":
        renderer.set_retrying(event.data)

    elif kind == "token":
        if not ctx.thinking:
            renderer.start_thinking(newline=True)
            ctx.thinking = True
        renderer.render_token(event.data["content"])
        renderer.increment_thinking_tokens()
        renderer.increment_streaming_chars(len(event.data.get("content", "")))
        renderer.update_thinking()
        enc = ctx.get_tiktoken_encoding() if ctx.get_tiktoken_encoding else None
        if enc:
            ctx.response_token_count += len(enc.encode(event.data["content"], allowed_special="all"))
        else:
            ctx.response_token_count += max(1, len(event.data["content"]) // 4)

    elif kind == "tool_call_start":
        if ctx.thinking:
            ctx.total_elapsed += await renderer.stop_thinking()
            ctx.thinking = False
        if ctx.plan_checklist_steps and ctx.plan_current_step[0] < len(ctx.plan_checklist_steps):
            idx = ctx.plan_current_step[0]
            renderer.update_plan_step(idx, "in_progress")
        renderer.render_tool_call_start(event.data["tool_name"], event.data["arguments"])

    elif kind == "tool_call_end":
        renderer.render_tool_call_end(event.data["tool_name"], event.data["status"], event.data["output"])

    elif kind == "auto_plan_suggest":
        if ctx.auto_plan_mode == "auto" and not ctx.plan_active[0]:
            if ctx.thinking:
                ctx.total_elapsed += await renderer.stop_thinking()
                ctx.thinking = False
            renderer.console.print(
                "\n[yellow]Complex task detected "
                f"({event.data['tool_calls']} tool calls). "
                "Switching to planning mode...[/yellow]\n"
            )
            ctx.cancel_event.set()
            if ctx.apply_plan_mode:
                ctx.apply_plan_mode(ctx.conv_id)
        elif ctx.auto_plan_mode == "suggest" and not ctx.plan_active[0]:
            if ctx.thinking:
                ctx.total_elapsed += await renderer.stop_thinking()
                ctx.thinking = False
            renderer.console.print(
                f"\n[yellow]This task looks complex "
                f"({event.data['tool_calls']} tool calls). "
                f"Consider using /plan for better results.[/yellow]\n"
            )
            renderer.start_thinking(newline=True)
            ctx.thinking = True

    elif kind == "usage":
        ctx.pending_usage = event.data

    elif kind == "assistant_message":
        if event.data["content"]:
            msg = storage.create_message(ctx.db, ctx.conv_id, "assistant", event.data["content"], **ctx.identity_kwargs)
            if ctx.pending_usage:
                storage.update_message_usage(
                    ctx.db,
                    msg["id"],
                    ctx.pending_usage.get("prompt_tokens", 0),
                    ctx.pending_usage.get("completion_tokens", 0),
                    ctx.pending_usage.get("total_tokens", 0),
                    ctx.pending_usage.get("model", ""),
                )
                ctx.pending_usage = None

    elif kind == "queued_message":
        if ctx.thinking:
            ctx.total_elapsed += await renderer.stop_thinking()
            ctx.thinking = False
        renderer.save_turn_history()
        renderer.render_newline()
        renderer.render_response_end()
        renderer.render_newline()
        renderer.console.print(f"[{CHROME}]Processing queued message...[/{CHROME}]")
        renderer.render_newline()
        renderer.clear_turn_history()
        ctx.response_token_count = 0

    elif kind == "error":
        error_msg = event.data.get("message", "Unknown error")
        retryable = event.data.get("retryable", False)
        if ctx.thinking and retryable and ctx.user_attempt < ctx.max_retries:
            ctx.should_retry = await renderer.thinking_countdown(ctx.retry_delay, ctx.cancel_event, error_msg)
            if ctx.should_retry and not ctx.cancel_event.is_set():
                ctx.cancel_event.clear()
                renderer.start_thinking()
            else:
                ctx.total_elapsed += await renderer.stop_thinking(cancel_msg="cancelled")
                ctx.thinking = False
        elif ctx.thinking and retryable and ctx.user_attempt >= ctx.max_retries:
            ctx.total_elapsed += await renderer.stop_thinking(
                error_msg=f"{error_msg} \u00b7 {ctx.user_attempt} attempts failed"
            )
            ctx.thinking = False
        elif ctx.thinking:
            ctx.total_elapsed += await renderer.stop_thinking(error_msg=error_msg)
            ctx.thinking = False
        else:
            renderer.render_error(error_msg)

    elif kind == "done":
        _finalize_plan_step(ctx)
        collapse = bool(ctx.plan_checklist_steps)
        if ctx.thinking and ctx.cancel_event.is_set():
            ctx.total_elapsed += await renderer.stop_thinking(cancel_msg="cancelled", collapse_plan=collapse)
            ctx.thinking = False
        elif ctx.thinking:
            ctx.total_elapsed += await renderer.stop_thinking(collapse_plan=collapse)
            ctx.thinking = False
        if ctx.plan_checklist_steps:
            ctx.plan_checklist_steps.clear()
            ctx.plan_current_step[0] = 0
        if not ctx.cancel_event.is_set():
            renderer.save_turn_history()
            renderer.render_response_end()
            renderer.render_newline()
            if ctx.estimate_tokens:
                context_tokens = ctx.estimate_tokens(ctx.ai_messages)
            else:
                context_tokens = 0
            renderer.render_context_footer(
                current_tokens=context_tokens,
                max_context=ctx.model_context_window,
                auto_compact_threshold=ctx.auto_compact_threshold,
                response_tokens=ctx.response_token_count,
                elapsed=ctx.total_elapsed,
            )
            renderer.render_newline()


def _advance_plan_step_complete(ctx: EventContext) -> None:
    """If a plan step was in_progress, mark it complete and advance."""
    if ctx.plan_checklist_steps and ctx.plan_current_step[0] < len(ctx.plan_checklist_steps):
        idx = ctx.plan_current_step[0]
        steps = renderer.get_plan_steps()
        if steps and idx < len(steps):
            step_state = steps[idx]
            if step_state.get("status") == "in_progress":
                renderer.update_plan_step(idx, "complete")
                ctx.plan_current_step[0] = idx + 1


def _finalize_plan_step(ctx: EventContext) -> None:
    """Mark any in-progress plan step as complete on done."""
    if ctx.plan_checklist_steps and ctx.plan_current_step[0] < len(ctx.plan_checklist_steps):
        idx = ctx.plan_current_step[0]
        steps = renderer.get_plan_steps()
        if steps and idx < len(steps):
            step_state = steps[idx]
            if step_state.get("status") == "in_progress":
                renderer.update_plan_step(idx, "complete")
