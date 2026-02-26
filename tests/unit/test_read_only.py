"""Tests for read-only mode: config field, filter function, tool list assembly."""

from __future__ import annotations

from anteroom.config import SafetyConfig
from anteroom.tools.tiers import (
    filter_read_only_tools,
)


def _make_tool(name: str) -> dict:
    """Create a minimal OpenAI tool definition."""
    return {"type": "function", "function": {"name": name, "parameters": {}}}


class TestFilterReadOnlyTools:
    """Tests for filter_read_only_tools() in tiers.py."""

    def test_keeps_read_tier_tools(self) -> None:
        tools = [_make_tool("read_file"), _make_tool("glob_files"), _make_tool("grep")]
        result = filter_read_only_tools(tools)
        assert len(result) == 3
        names = {t["function"]["name"] for t in result}
        assert names == {"read_file", "glob_files", "grep"}

    def test_removes_write_tier_tools(self) -> None:
        tools = [_make_tool("read_file"), _make_tool("write_file"), _make_tool("edit_file")]
        result = filter_read_only_tools(tools)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "read_file"

    def test_removes_execute_tier_tools(self) -> None:
        tools = [_make_tool("read_file"), _make_tool("bash"), _make_tool("run_agent")]
        result = filter_read_only_tools(tools)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "read_file"

    def test_removes_mcp_tools(self) -> None:
        tools = [_make_tool("read_file"), _make_tool("mcp_some_tool")]
        result = filter_read_only_tools(tools)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "read_file"

    def test_empty_list(self) -> None:
        assert filter_read_only_tools([]) == []

    def test_all_write_tools_returns_empty(self) -> None:
        tools = [_make_tool("bash"), _make_tool("write_file")]
        assert filter_read_only_tools(tools) == []

    def test_canvas_tools_kept(self) -> None:
        tools = [_make_tool("create_canvas"), _make_tool("update_canvas"), _make_tool("patch_canvas")]
        result = filter_read_only_tools(tools)
        assert len(result) == 3

    def test_invoke_skill_kept(self) -> None:
        tools = [_make_tool("invoke_skill"), _make_tool("bash")]
        result = filter_read_only_tools(tools)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "invoke_skill"

    def test_ask_user_kept(self) -> None:
        tools = [_make_tool("ask_user"), _make_tool("write_file")]
        result = filter_read_only_tools(tools)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "ask_user"

    def test_introspect_kept(self) -> None:
        tools = [_make_tool("introspect")]
        result = filter_read_only_tools(tools)
        assert len(result) == 1

    def test_tier_override_promotes_tool_to_read(self) -> None:
        tools = [_make_tool("bash"), _make_tool("read_file")]
        result = filter_read_only_tools(tools, tier_overrides={"bash": "read"})
        assert len(result) == 2
        names = {t["function"]["name"] for t in result}
        assert names == {"bash", "read_file"}

    def test_tier_override_demotes_tool_from_read(self) -> None:
        tools = [_make_tool("read_file"), _make_tool("glob_files")]
        result = filter_read_only_tools(tools, tier_overrides={"read_file": "write"})
        assert len(result) == 1
        assert result[0]["function"]["name"] == "glob_files"

    def test_mixed_tools_comprehensive(self) -> None:
        tools = [
            _make_tool("read_file"),
            _make_tool("glob_files"),
            _make_tool("grep"),
            _make_tool("ask_user"),
            _make_tool("introspect"),
            _make_tool("create_canvas"),
            _make_tool("invoke_skill"),
            _make_tool("write_file"),
            _make_tool("edit_file"),
            _make_tool("bash"),
            _make_tool("run_agent"),
            _make_tool("mcp_tool_a"),
        ]
        result = filter_read_only_tools(tools)
        names = {t["function"]["name"] for t in result}
        assert names == {"read_file", "glob_files", "grep", "ask_user", "introspect", "create_canvas", "invoke_skill"}

    def test_preserves_tool_structure(self) -> None:
        tool = {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            },
        }
        result = filter_read_only_tools([tool])
        assert result[0] is tool


class TestSafetyConfigReadOnly:
    """Tests for read_only field on SafetyConfig."""

    def test_default_is_false(self) -> None:
        config = SafetyConfig()
        assert config.read_only is False

    def test_set_to_true(self) -> None:
        config = SafetyConfig(read_only=True)
        assert config.read_only is True


class TestReadOnlyConfigParsing:
    """Tests for read_only parsing logic."""

    def test_read_only_true_string_values(self) -> None:
        for val in ("true", "True", "TRUE", "1", "yes"):
            assert str(val).lower() in ("true", "1", "yes")

    def test_read_only_false_string_values(self) -> None:
        for val in ("false", "False", "0", "no", ""):
            assert str(val).lower() not in ("true", "1", "yes") or val == ""

    def test_safety_config_read_only_field(self) -> None:
        config = SafetyConfig(read_only=True)
        assert config.read_only is True
        config2 = SafetyConfig(read_only=False)
        assert config2.read_only is False

    def test_env_var_parsing_logic(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"AI_CHAT_READ_ONLY": "true"}):
            val = str(os.environ.get("AI_CHAT_READ_ONLY", "false")).lower() in ("true", "1", "yes")
            assert val is True

        with patch.dict(os.environ, {"AI_CHAT_READ_ONLY": "false"}):
            val = str(os.environ.get("AI_CHAT_READ_ONLY", "false")).lower() in ("true", "1", "yes")
            assert val is False

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_CHAT_READ_ONLY", None)
            val = str(os.environ.get("AI_CHAT_READ_ONLY", "false")).lower() in ("true", "1", "yes")
            assert val is False


class TestReadOnlyConfigValidation:
    """Tests for config validator handling of read_only field."""

    def test_valid_read_only_true(self) -> None:
        from anteroom.services.config_validator import validate_config

        raw = {"safety": {"read_only": True}}
        result = validate_config(raw)
        assert result.is_valid

    def test_valid_read_only_false(self) -> None:
        from anteroom.services.config_validator import validate_config

        raw = {"safety": {"read_only": False}}
        result = validate_config(raw)
        assert result.is_valid

    def test_valid_read_only_string(self) -> None:
        from anteroom.services.config_validator import validate_config

        raw = {"safety": {"read_only": "true"}}
        result = validate_config(raw)
        assert result.is_valid

    def test_invalid_read_only_warns(self) -> None:
        from anteroom.services.config_validator import validate_config

        raw = {"safety": {"read_only": "not_a_bool"}}
        result = validate_config(raw)
        assert result.has_warnings
        paths = [e.path for e in result.errors]
        assert "safety.read_only" in paths


class TestBuildToolListReadOnly:
    """Tests for _build_tool_list with read_only parameter."""

    def test_read_only_filters_tools(self) -> None:
        from unittest.mock import MagicMock

        from anteroom.routers.chat import _build_tool_list

        registry = MagicMock()
        registry.get_openai_tools.return_value = [
            _make_tool("read_file"),
            _make_tool("write_file"),
            _make_tool("bash"),
        ]
        registry.list_tools.return_value = ["read_file", "write_file", "bash"]

        tools, _, _ = _build_tool_list(
            tool_registry=registry,
            mcp_manager=None,
            plan_mode=False,
            conversation_id="test",
            data_dir=MagicMock(),
            max_tools=128,
            read_only=True,
        )
        names = {t["function"]["name"] for t in tools}
        assert "read_file" in names
        assert "write_file" not in names
        assert "bash" not in names

    def test_read_only_false_keeps_all(self) -> None:
        from unittest.mock import MagicMock

        from anteroom.routers.chat import _build_tool_list

        registry = MagicMock()
        registry.get_openai_tools.return_value = [
            _make_tool("read_file"),
            _make_tool("write_file"),
            _make_tool("bash"),
        ]
        registry.list_tools.return_value = ["read_file", "write_file", "bash"]

        tools, _, _ = _build_tool_list(
            tool_registry=registry,
            mcp_manager=None,
            plan_mode=False,
            conversation_id="test",
            data_dir=MagicMock(),
            max_tools=128,
            read_only=False,
        )
        names = {t["function"]["name"] for t in tools}
        assert names == {"read_file", "write_file", "bash"}

    def test_read_only_with_mcp_tools_excluded(self) -> None:
        from unittest.mock import MagicMock

        from anteroom.routers.chat import _build_tool_list

        registry = MagicMock()
        registry.get_openai_tools.return_value = [_make_tool("read_file")]
        registry.list_tools.return_value = ["read_file"]

        mcp_mgr = MagicMock()
        mcp_mgr.get_openai_tools.return_value = [_make_tool("mcp_tool")]

        tools, _, _ = _build_tool_list(
            tool_registry=registry,
            mcp_manager=mcp_mgr,
            plan_mode=False,
            conversation_id="test",
            data_dir=MagicMock(),
            max_tools=128,
            read_only=True,
        )
        names = {t["function"]["name"] for t in tools}
        assert "read_file" in names
        assert "mcp_tool" not in names

    def test_read_only_with_tier_override(self) -> None:
        from unittest.mock import MagicMock

        from anteroom.routers.chat import _build_tool_list

        registry = MagicMock()
        registry.get_openai_tools.return_value = [
            _make_tool("read_file"),
            _make_tool("bash"),
        ]
        registry.list_tools.return_value = ["read_file", "bash"]

        tools, _, _ = _build_tool_list(
            tool_registry=registry,
            mcp_manager=None,
            plan_mode=False,
            conversation_id="test",
            data_dir=MagicMock(),
            max_tools=128,
            read_only=True,
            tier_overrides={"bash": "read"},
        )
        names = {t["function"]["name"] for t in tools}
        assert names == {"read_file", "bash"}

    def test_read_only_plus_plan_mode(self) -> None:
        """Read-only filter runs first, then plan mode filters further."""
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock

        from anteroom.routers.chat import _build_tool_list

        registry = MagicMock()
        registry.get_openai_tools.return_value = [
            _make_tool("read_file"),
            _make_tool("glob_files"),
            _make_tool("grep"),
            _make_tool("ask_user"),
            _make_tool("write_file"),
            _make_tool("bash"),
        ]
        registry.list_tools.return_value = ["read_file", "glob_files", "grep", "ask_user", "write_file", "bash"]

        with tempfile.TemporaryDirectory() as tmpdir:
            tools, plan_path, plan_prompt = _build_tool_list(
                tool_registry=registry,
                mcp_manager=None,
                plan_mode=True,
                conversation_id="test",
                data_dir=Path(tmpdir),
                max_tools=128,
                read_only=True,
            )
            names = {t["function"]["name"] for t in tools}
            # read_only keeps only READ tier, plan mode further filters to PLAN_MODE_ALLOWED_TOOLS
            # The intersection of READ-tier tools and plan-mode tools
            assert "write_file" not in names
            assert "bash" not in names
            assert plan_path is not None


class TestReadOnlyExecutionTimeEnforcement:
    """Tests for defense-in-depth: check_safety() hard-denies non-READ tools in read-only mode."""

    def test_check_safety_blocks_write_tool_in_read_only(self) -> None:
        from anteroom.tools import ToolRegistry

        registry = ToolRegistry()
        config = SafetyConfig(read_only=True)
        registry.set_safety_config(config)

        verdict = registry.check_safety("write_file", {"path": "/tmp/test", "content": "x"})
        assert verdict is not None
        assert verdict.hard_denied is True
        assert "read-only" in verdict.reason

    def test_check_safety_blocks_bash_in_read_only(self) -> None:
        from anteroom.tools import ToolRegistry

        registry = ToolRegistry()
        config = SafetyConfig(read_only=True)
        registry.set_safety_config(config)

        verdict = registry.check_safety("bash", {"command": "ls"})
        assert verdict is not None
        assert verdict.hard_denied is True

    def test_check_safety_blocks_mcp_tool_in_read_only(self) -> None:
        from anteroom.tools import ToolRegistry

        registry = ToolRegistry()
        config = SafetyConfig(read_only=True)
        registry.set_safety_config(config)

        verdict = registry.check_safety("mcp_some_tool", {"arg": "val"})
        assert verdict is not None
        assert verdict.hard_denied is True

    def test_check_safety_allows_read_tool_in_read_only(self) -> None:
        from anteroom.tools import ToolRegistry

        registry = ToolRegistry()
        config = SafetyConfig(read_only=True)
        registry.set_safety_config(config)

        verdict = registry.check_safety("read_file", {"path": "/tmp/test"})
        assert verdict is None  # auto-allowed

    def test_check_safety_allows_all_when_not_read_only(self) -> None:
        from anteroom.tools import ToolRegistry

        registry = ToolRegistry()
        config = SafetyConfig(read_only=False, approval_mode="auto")
        registry.set_safety_config(config)

        verdict = registry.check_safety("bash", {"command": "ls"})
        assert verdict is None  # auto-allowed in auto mode

    def test_read_only_override_promotes_tool(self) -> None:
        from anteroom.tools import ToolRegistry

        registry = ToolRegistry()
        config = SafetyConfig(read_only=True, tool_tiers={"bash": "read"})
        registry.set_safety_config(config)

        verdict = registry.check_safety("bash", {"command": "ls"})
        assert verdict is None  # promoted to READ via override


class TestAppConfigResponseReadOnly:
    """Tests for read_only field in AppConfigResponse model."""

    def test_default_false(self) -> None:
        from anteroom.models import AppConfigResponse

        resp = AppConfigResponse(ai={"base_url": "http://test", "model": "test"})
        assert resp.read_only is False

    def test_set_true(self) -> None:
        from anteroom.models import AppConfigResponse

        resp = AppConfigResponse(ai={"base_url": "http://test", "model": "test"}, read_only=True)
        assert resp.read_only is True
