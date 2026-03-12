"""Tests pinning /a-help prompt behavioral contracts and CLI invocation path."""

from __future__ import annotations

from pathlib import Path

import pytest

_A_HELP_PATH = Path(__file__).resolve().parents[2] / "src" / "anteroom" / "cli" / "default_skills" / "a-help.yaml"


class TestAHelpPromptContract:
    """Pin that the a-help prompt contains required structural elements."""

    @pytest.fixture()
    def prompt(self) -> str:
        import yaml

        text = _A_HELP_PATH.read_text()
        data = yaml.safe_load(text)
        return data["prompt"]

    def test_docs_first_strategy(self, prompt: str) -> None:
        assert "Check the inline quick reference FIRST" in prompt

    def test_has_source_code_index(self, prompt: str) -> None:
        assert "Source Code Index" in prompt

    def test_has_introspect_guidance(self, prompt: str) -> None:
        assert "introspect section=package" in prompt

    def test_has_scope_guardrail(self, prompt: str) -> None:
        assert "Anteroom's own installed" in prompt or "do not read arbitrary user project files" in prompt

    def test_under_size_budget(self) -> None:
        size = _A_HELP_PATH.stat().st_size
        assert size < 15_000, f"a-help.yaml is {size} bytes, budget is 15,000 bytes"


class TestAHelpCliInvocationPath:
    """Verify /a-help resolves through SkillRegistry.resolve_input() — the CLI path."""

    def test_resolves_via_resolve_input(self) -> None:
        from anteroom.cli.skills import SkillRegistry

        reg = SkillRegistry()
        reg.load()
        is_skill, expanded_prompt = reg.resolve_input("/a-help how does the agent loop work?")
        assert is_skill is True
        assert "how does the agent loop work?" in expanded_prompt
        assert "Source Code Index" in expanded_prompt
