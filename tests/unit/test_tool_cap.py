"""Tests for the cap_tools() helper (#311)."""

from __future__ import annotations

import logging
from typing import Any

from anteroom.tools import cap_tools


def _tool(name: str) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": f"{name} tool", "parameters": {}}}


BUILTIN_NAMES = {"read_file", "write_file", "bash"}


class TestCapToolsPassthrough:
    def test_under_limit_returns_unchanged(self) -> None:
        tools = [_tool("read_file"), _tool("bash"), _tool("mcp_a")]
        result = cap_tools(tools, BUILTIN_NAMES, limit=128)
        assert result == tools

    def test_at_limit_returns_unchanged(self) -> None:
        tools = [_tool(f"tool_{i}") for i in range(128)]
        result = cap_tools(tools, set(), limit=128)
        assert len(result) == 128

    def test_empty_list_returns_empty(self) -> None:
        result = cap_tools([], BUILTIN_NAMES, limit=128)
        assert result == []

    def test_zero_limit_means_unlimited(self) -> None:
        tools = [_tool(f"tool_{i}") for i in range(200)]
        result = cap_tools(tools, set(), limit=0)
        assert len(result) == 200


class TestCapToolsTruncation:
    def test_over_limit_truncated(self) -> None:
        tools = [_tool(f"tool_{i}") for i in range(200)]
        result = cap_tools(tools, set(), limit=128)
        assert len(result) == 128

    def test_builtin_tools_always_kept(self) -> None:
        builtins = [_tool(n) for n in BUILTIN_NAMES]
        mcp = [_tool(f"mcp_{i}") for i in range(130)]
        tools = builtins + mcp
        result = cap_tools(tools, BUILTIN_NAMES, limit=5)
        names = {t["function"]["name"] for t in result}
        for n in BUILTIN_NAMES:
            assert n in names
        assert len(result) == 5

    def test_mcp_tools_sorted_alphabetically(self) -> None:
        mcp = [_tool("z_tool"), _tool("a_tool"), _tool("m_tool")]
        result = cap_tools(mcp, set(), limit=2)
        names = [t["function"]["name"] for t in result]
        assert names == ["a_tool", "m_tool"]

    def test_custom_limit_respected(self) -> None:
        tools = [_tool(f"t_{i}") for i in range(50)]
        result = cap_tools(tools, set(), limit=10)
        assert len(result) == 10

    def test_all_builtin_exceeds_limit_keeps_all_builtin(self) -> None:
        """When builtin count alone exceeds limit, keep all builtins, zero MCP."""
        builtin_names = {f"builtin_{i}" for i in range(10)}
        builtins = [_tool(n) for n in sorted(builtin_names)]
        mcp = [_tool("mcp_a"), _tool("mcp_b")]
        tools = builtins + mcp
        result = cap_tools(tools, builtin_names, limit=5)
        names = {t["function"]["name"] for t in result}
        assert builtin_names.issubset(names)
        assert "mcp_a" not in names
        assert "mcp_b" not in names


class TestCapToolsLogging:
    def test_warning_logged_when_tools_dropped(self, caplog: Any) -> None:
        tools = [_tool("builtin_a")] + [_tool(f"mcp_{i}") for i in range(10)]
        with caplog.at_level(logging.WARNING, logger="anteroom.tools"):
            cap_tools(tools, {"builtin_a"}, limit=5)
        assert any("dropped" in r.message.lower() for r in caplog.records)

    def test_no_warning_when_under_limit(self, caplog: Any) -> None:
        tools = [_tool("a"), _tool("b")]
        with caplog.at_level(logging.WARNING, logger="anteroom.tools"):
            cap_tools(tools, set(), limit=128)
        assert not any("dropped" in r.message.lower() for r in caplog.records)

    def test_warning_lists_dropped_tool_names(self, caplog: Any) -> None:
        tools = [_tool("mcp_alpha"), _tool("mcp_beta"), _tool("mcp_gamma")]
        with caplog.at_level(logging.WARNING, logger="anteroom.tools"):
            cap_tools(tools, set(), limit=1)
        warning = next(r for r in caplog.records if "dropped" in r.message.lower())
        assert "mcp_beta" in warning.message
        assert "mcp_gamma" in warning.message
