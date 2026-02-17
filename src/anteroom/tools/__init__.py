"""Built-in tool registry for the agentic CLI."""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

from ..config import SafetyConfig
from .safety import SafetyVerdict, check_bash_command, check_write_path

logger = logging.getLogger(__name__)

ToolHandler = Callable[..., Coroutine[Any, Any, dict[str, Any]]]
ConfirmCallback = Callable[[SafetyVerdict], Coroutine[Any, Any, bool]]


class ToolRegistry:
    """Registry of built-in tools with OpenAI function-call format."""

    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        self._definitions: dict[str, dict[str, Any]] = {}
        self._confirm_callback: ConfirmCallback | None = None
        self._safety_config: SafetyConfig | None = None
        self._working_dir: str | None = None

    def set_confirm_callback(self, callback: ConfirmCallback | None) -> None:
        self._confirm_callback = callback

    def set_safety_config(self, config: SafetyConfig, working_dir: str | None = None) -> None:
        self._safety_config = config
        self._working_dir = working_dir

    def register(self, name: str, handler: ToolHandler, definition: dict[str, Any]) -> None:
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

    def _check_safety(self, tool_name: str, arguments: dict[str, Any]) -> SafetyVerdict | None:
        config = self._safety_config
        if not config or not config.enabled:
            return None

        if tool_name == "bash" and config.bash.enabled:
            command = arguments.get("command", "")
            return check_bash_command(command, custom_patterns=config.custom_patterns)

        if tool_name == "write_file" and config.write_file.enabled:
            path = arguments.get("path", "")
            working_dir = self._working_dir or "."
            return check_write_path(path, working_dir, sensitive_paths=config.sensitive_paths)

        return None

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        confirm_callback: ConfirmCallback | None = None,
    ) -> dict[str, Any]:
        handler = self._handlers.get(name)
        if not handler:
            raise ValueError(f"Unknown built-in tool: {name}")

        verdict = self._check_safety(name, arguments)
        if verdict and verdict.needs_approval:
            callback = confirm_callback or self._confirm_callback
            if callback is None:
                logger.warning("Safety gate blocked (no approval channel): %s", verdict.reason)
                return {"error": "Operation blocked: no approval channel available", "safety_blocked": True}
            confirmed = await callback(verdict)
            if not confirmed:
                return {"error": "Operation denied by user", "exit_code": -1}

        return await handler(**arguments)

    def list_tools(self) -> list[str]:
        return list(self._handlers.keys())


def register_default_tools(registry: ToolRegistry, working_dir: str | None = None) -> None:
    """Register all built-in tools."""
    from . import bash, edit, glob_tool, grep, read, write
    from .canvas import (
        CANVAS_CREATE_DEFINITION,
        CANVAS_PATCH_DEFINITION,
        CANVAS_UPDATE_DEFINITION,
        handle_create_canvas,
        handle_patch_canvas,
        handle_update_canvas,
    )

    for module in [read, write, edit, bash, glob_tool, grep]:
        handler = module.handle
        defn = module.DEFINITION
        if working_dir and hasattr(module, "set_working_dir"):
            module.set_working_dir(working_dir)
        registry.register(defn["name"], handler, defn)

    registry.register(CANVAS_CREATE_DEFINITION["name"], handle_create_canvas, CANVAS_CREATE_DEFINITION)
    registry.register(CANVAS_UPDATE_DEFINITION["name"], handle_update_canvas, CANVAS_UPDATE_DEFINITION)
    registry.register(CANVAS_PATCH_DEFINITION["name"], handle_patch_canvas, CANVAS_PATCH_DEFINITION)
