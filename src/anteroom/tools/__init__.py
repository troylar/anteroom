"""Built-in tool registry for the agentic CLI."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

ToolHandler = Callable[..., Coroutine[Any, Any, dict[str, Any]]]
ConfirmCallback = Callable[[str], Coroutine[Any, Any, bool]]

# Destructive command patterns that need confirmation.
# These are regexes searched against a normalized command string.
_DESTRUCTIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brm\s+", re.IGNORECASE),
    re.compile(r"\brmdir\b", re.IGNORECASE),
    re.compile(r"\bgit\s+push\s+(-f|--force)\b", re.IGNORECASE),
    re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE),
    re.compile(r"\bgit\s+clean\b", re.IGNORECASE),
    re.compile(r"\bgit\s+checkout\s+\.\b", re.IGNORECASE),
    re.compile(r"\bdrop\s+table\b", re.IGNORECASE),
    re.compile(r"\bdrop\s+database\b", re.IGNORECASE),
    re.compile(r"\btruncate\s+", re.IGNORECASE),
    re.compile(r">\s*/dev/", re.IGNORECASE),
    re.compile(r"\bchmod\s+777\b", re.IGNORECASE),
    re.compile(r"\bkill\s+-9\b", re.IGNORECASE),
)


def _normalize_command(command: str) -> str:
    # Collapse any whitespace runs (spaces, tabs, newlines) to a single space.
    return re.sub(r"\s+", " ", command).strip().lower()


def _is_destructive_command(command: str) -> bool:
    cmd = _normalize_command(command)
    return any(p.search(cmd) is not None for p in _DESTRUCTIVE_PATTERNS)


class ToolRegistry:
    """Registry of built-in tools with OpenAI function-call format."""

    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        self._definitions: dict[str, dict[str, Any]] = {}
        self._confirm_callback: ConfirmCallback | None = None

    def set_confirm_callback(self, callback: ConfirmCallback) -> None:
        """Set callback for confirming destructive operations."""
        self._confirm_callback = callback

    def register(
        self, name: str, handler: ToolHandler, definition: dict[str, Any]
    ) -> None:
        self._handlers[name] = handler
        self._definitions[name] = definition

    def has_tool(self, name: str) -> bool:
        return name in self._handlers

    def get_openai_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": defn.get("description", ""),
                    "parameters": defn.get("parameters", {}),
                },
            }
            for name, defn in self._definitions.items()
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler = self._handlers.get(name)
        if not handler:
            raise ValueError(f"Unknown built-in tool: {name}")

        # Check for destructive operations
        if self._confirm_callback and name == "bash":
            command = arguments.get("command", "")
            if _is_destructive_command(command):
                confirmed = await self._confirm_callback(
                    f"Destructive command: {command}"
                )
                if not confirmed:
                    return {"error": "Command cancelled by user", "exit_code": -1}

        return await handler(**arguments)

    def list_tools(self) -> list[str]:
        return list(self._handlers.keys())


def register_default_tools(
    registry: ToolRegistry, working_dir: str | None = None
) -> None:
    """Register all built-in tools."""
    from . import bash, edit, glob_tool, grep, read, write

    for module in [read, write, edit, bash, glob_tool, grep]:
        handler = module.handle
        defn = module.DEFINITION
        if working_dir and hasattr(module, "set_working_dir"):
            module.set_working_dir(working_dir)
        registry.register(defn["name"], handler, defn)
