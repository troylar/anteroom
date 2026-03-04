"""Tests for the Excalidraw skill and canvas integration."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from anteroom.cli.skills import SkillRegistry
from anteroom.tools.canvas import (
    CANVAS_CREATE_DEFINITION,
    handle_create_canvas,
)

_SKILL_PATH = Path(__file__).resolve().parents[2] / "src" / "anteroom" / "cli" / "default_skills" / "excalidraw.yaml"

_SAMPLE_EXCALIDRAW = json.dumps(
    {
        "type": "excalidraw",
        "version": 2,
        "elements": [
            {
                "id": "rect-1",
                "type": "rectangle",
                "x": 100,
                "y": 100,
                "width": 200,
                "height": 100,
                "strokeColor": "#000000",
                "backgroundColor": "transparent",
                "fillStyle": "hachure",
                "strokeWidth": 1,
                "roughness": 1,
                "seed": 12345,
                "version": 1,
                "versionNonce": 67890,
                "isDeleted": False,
                "boundElements": None,
                "link": None,
                "locked": False,
                "updated": 1700000000000,
            }
        ],
        "appState": {"viewBackgroundColor": "#ffffff"},
    }
)


class TestExcalidrawSkillYaml:
    """Verify the excalidraw.yaml skill file is valid and loadable."""

    def test_yaml_file_exists(self) -> None:
        assert _SKILL_PATH.exists(), f"Skill YAML not found at {_SKILL_PATH}"

    def test_yaml_parses_correctly(self) -> None:
        data = yaml.safe_load(_SKILL_PATH.read_text())
        assert isinstance(data, dict)

    def test_has_required_fields(self) -> None:
        data = yaml.safe_load(_SKILL_PATH.read_text())
        assert data.get("name") == "excalidraw"
        assert "description" in data
        assert "prompt" in data
        assert len(data["prompt"]) > 100  # substantial prompt

    def test_prompt_mentions_create_canvas(self) -> None:
        data = yaml.safe_load(_SKILL_PATH.read_text())
        prompt = data["prompt"]
        assert "create_canvas" in prompt
        assert "excalidraw" in prompt.lower()

    def test_prompt_has_args_placeholder(self) -> None:
        data = yaml.safe_load(_SKILL_PATH.read_text())
        assert "{args}" in data["prompt"]

    def test_loaded_by_skill_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            reg = SkillRegistry()
            reg.load(tmpdir)
            names = [s.name for s in reg.list_skills()]
            assert "excalidraw" in names


class TestCanvasToolExcalidrawLanguage:
    """Verify canvas tools accept language='excalidraw'."""

    def test_create_definition_language_mentions_excalidraw(self) -> None:
        lang_desc = CANVAS_CREATE_DEFINITION["parameters"]["properties"]["language"]["description"]
        assert "excalidraw" in lang_desc.lower()

    @pytest.fixture()
    def mock_storage(self) -> MagicMock:
        mock = MagicMock()
        with patch.dict(sys.modules, {"anteroom.services.storage": mock}):
            import anteroom.services

            original = getattr(anteroom.services, "storage", None)
            anteroom.services.storage = mock
            yield mock
            if original is not None:
                anteroom.services.storage = original
            elif hasattr(anteroom.services, "storage"):
                delattr(anteroom.services, "storage")

    @pytest.mark.asyncio()
    async def test_create_canvas_with_excalidraw(self, mock_storage: MagicMock) -> None:
        mock_storage.get_conversation.return_value = {"id": "conv-1"}
        mock_storage.get_canvas_for_conversation.return_value = None
        mock_storage.create_canvas.return_value = {
            "id": "canvas-1",
            "title": "Architecture Diagram",
            "language": "excalidraw",
            "content": _SAMPLE_EXCALIDRAW,
        }

        result = await handle_create_canvas(
            title="Architecture Diagram",
            content=_SAMPLE_EXCALIDRAW,
            language="excalidraw",
            _conversation_id="conv-1",
            _db=MagicMock(),
        )

        assert result["status"] == "created"
        assert result["language"] == "excalidraw"
        mock_storage.create_canvas.assert_called_once()
        call_kwargs = mock_storage.create_canvas.call_args
        assert call_kwargs[1]["language"] == "excalidraw"

    @pytest.mark.asyncio()
    async def test_excalidraw_json_roundtrips(self, mock_storage: MagicMock) -> None:
        """Verify Excalidraw JSON content passes through create_canvas unchanged."""
        mock_storage.get_conversation.return_value = {"id": "conv-1"}
        mock_storage.get_canvas_for_conversation.return_value = None
        mock_storage.create_canvas.return_value = {
            "id": "c-1",
            "title": "Test",
            "language": "excalidraw",
            "content": _SAMPLE_EXCALIDRAW,
        }

        await handle_create_canvas(
            title="Test",
            content=_SAMPLE_EXCALIDRAW,
            language="excalidraw",
            _conversation_id="conv-1",
            _db=MagicMock(),
        )

        stored_content = mock_storage.create_canvas.call_args[1]["content"]
        parsed = json.loads(stored_content)
        assert parsed["type"] == "excalidraw"
        assert len(parsed["elements"]) == 1
        assert parsed["elements"][0]["type"] == "rectangle"

    @pytest.mark.asyncio()
    async def test_excalidraw_content_size_limit(self, mock_storage: MagicMock) -> None:
        """Excalidraw content is subject to the same size limit as other canvas content."""
        mock_storage.get_conversation.return_value = {"id": "conv-1"}
        mock_storage.get_canvas_for_conversation.return_value = None

        large_content = "x" * 100_001
        result = await handle_create_canvas(
            title="Big",
            content=large_content,
            language="excalidraw",
            _conversation_id="conv-1",
            _db=MagicMock(),
        )

        assert "error" in result
        assert "too large" in result["error"].lower()
