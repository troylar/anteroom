"""Planning mode helpers: file I/O and system prompt construction."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_PLAN_SUBCOMMANDS = frozenset({"on", "start", "approve", "status", "edit", "off"})

# Tools allowed during plan mode — read-only exploration plus write_file for the plan itself
PLAN_MODE_ALLOWED_TOOLS = frozenset(
    {
        "read_file",
        "glob_files",
        "grep",
        "bash",
        "write_file",
        "run_agent",
    }
)


def get_plan_file_path(data_dir: Path, conversation_id: str) -> Path:
    """Return the plan file path for a conversation, creating the plans/ dir.

    Raises ValueError if conversation_id contains path traversal.
    """
    plans_dir = data_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_path = (plans_dir / f"{conversation_id}.md").resolve()
    if not str(plan_path).startswith(str(plans_dir.resolve())):
        raise ValueError("Invalid conversation_id")
    return plan_path


def build_planning_system_prompt(plan_file_path: Path) -> str:
    """Return a system prompt section that constrains the AI to planning mode."""
    return (
        "<planning_mode>\n"
        "You are in PLANNING MODE. Your job is to explore the codebase, gather information, "
        "and write a detailed implementation plan — NOT to implement anything.\n\n"
        "Rules:\n"
        "- Use read_file, glob_files, grep, and bash to explore the codebase\n"
        "- You MUST NOT create, edit, or delete any files EXCEPT the plan file below\n"
        "- When you have gathered enough information, write your plan using write_file to:\n"
        f"  {plan_file_path}\n\n"
        "Plan format (Markdown):\n"
        "- ## Overview — what the task is and the approach\n"
        "- ## Files to Change — list of files with what changes are needed\n"
        "- ## Implementation Steps — ordered steps with details\n"
        "- ## Test Strategy — what tests to add or modify\n\n"
        "When the plan is written, tell the user it is ready and they can review it with "
        "`/plan status` and approve it with `/plan approve`.\n"
        "</planning_mode>"
    )


def read_plan(plan_file_path: Path) -> str | None:
    """Read the plan file, returning None if it doesn't exist."""
    if not plan_file_path.exists():
        return None
    return plan_file_path.read_text(encoding="utf-8")


def get_editor() -> str:
    """Resolve the user's preferred editor: $VISUAL > $EDITOR > vi."""
    return os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"


def delete_plan(plan_file_path: Path) -> None:
    """Delete the plan file if it exists."""
    if plan_file_path.exists():
        plan_file_path.unlink()


def parse_plan_steps(plan_content: str) -> list[str]:
    """Extract implementation steps from a plan markdown file.

    Looks for a section headed ``## Implementation Steps`` (case-insensitive)
    and extracts numbered or bulleted list items from it.  Stops at the next
    ``##`` heading or end of file.

    Returns a list of step descriptions (stripped of leading numbers/bullets).
    """
    # Find the Implementation Steps section
    pattern = re.compile(r"^##\s+Implementation\s+Steps\b", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(plan_content)
    if not match:
        return []

    # Extract content from after the heading to the next ## heading
    start = match.end()
    next_heading = re.search(r"^##\s+", plan_content[start:], re.MULTILINE)
    section = plan_content[start : start + next_heading.start()] if next_heading else plan_content[start:]

    # Parse list items: "1. ...", "- ...", "* ...", "1) ..."
    steps: list[str] = []
    item_re = re.compile(r"^\s*(?:\d+[\.\)]\s+|[-*]\s+)(.+)", re.MULTILINE)
    for m in item_re.finditer(section):
        text = m.group(1).strip()
        # Strip trailing markdown formatting like **bold**
        if text:
            steps.append(text)

    return steps


def parse_plan_command(user_input: str) -> tuple[str | None, str | None]:
    """Parse a /plan command into (subcommand, inline_prompt).

    Returns:
        (subcommand, None) for known subcommands like "on", "approve", etc.
        (None, prompt_text) for inline prompts like "/plan build a REST API".
        ("on", None) when no arguments are given (default behavior).
    """
    parts = user_input.split()
    if len(parts) < 2:
        return ("on", None)
    candidate = parts[1].lower()
    if candidate in _PLAN_SUBCOMMANDS:
        return (candidate, None)
    # Everything after "/plan " is the inline prompt
    prompt = user_input.split(maxsplit=1)[1] if len(user_input.split(maxsplit=1)) > 1 else ""
    return (None, prompt if prompt else None)


def strip_planning_prompt(prompt: str) -> str:
    """Remove the ``<planning_mode>`` XML block from a system prompt."""
    return re.sub(r"\n*<planning_mode>.*?</planning_mode>", "", prompt, flags=re.DOTALL)


def enter_plan_mode(
    conv_id: str,
    data_dir: Path,
    plan_active: list[bool],
    plan_file: list[Path | None],
    full_tools_backup: list[list[dict[str, Any]] | None],
    tools_openai: list[dict[str, Any]] | None,
    extra_system_prompt: str,
) -> tuple[list[dict[str, Any]] | None, str]:
    """Activate plan mode: filter tools, inject planning prompt.

    Returns the updated (tools_openai, extra_system_prompt).
    """
    plan_path = get_plan_file_path(data_dir, conv_id)
    plan_file[0] = plan_path
    plan_active[0] = True
    full_tools_backup[0] = tools_openai

    if tools_openai:
        tools_openai = [t for t in tools_openai if t.get("function", {}).get("name") in PLAN_MODE_ALLOWED_TOOLS]

    extra_system_prompt = strip_planning_prompt(extra_system_prompt)
    extra_system_prompt += "\n\n" + build_planning_system_prompt(plan_path)

    return tools_openai, extra_system_prompt


def leave_plan_mode(
    plan_active: list[bool],
    full_tools_backup: list[list[dict[str, Any]] | None],
    extra_system_prompt: str,
    rebuild_tools_fn: Any | None = None,
    plan_content: str | None = None,
) -> tuple[list[dict[str, Any]] | None, str]:
    """Deactivate plan mode: restore tools, optionally inject approved plan.

    Returns the updated (tools_openai, extra_system_prompt).
    """
    plan_active[0] = False

    if full_tools_backup[0] is not None:
        tools_openai = full_tools_backup[0]
        full_tools_backup[0] = None
    elif rebuild_tools_fn:
        rebuild_tools_fn()
        tools_openai = None  # rebuilt externally
    else:
        tools_openai = None

    extra_system_prompt = strip_planning_prompt(extra_system_prompt)
    if plan_content:
        extra_system_prompt += (
            "\n\n<approved_plan>\n"
            "The user has approved the following implementation plan. "
            "Execute it step by step.\n\n" + plan_content + "\n</approved_plan>"
        )

    return tools_openai, extra_system_prompt
