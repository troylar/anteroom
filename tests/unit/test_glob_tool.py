"""Tests for tools/glob_tool.py (#689)."""

from __future__ import annotations

from pathlib import Path

import pytest

from anteroom.tools.glob_tool import handle, set_working_dir


@pytest.fixture()
def tmp_tree(tmp_path: Path) -> Path:
    (tmp_path / "hello.py").write_text("print('hello')\n")
    (tmp_path / "data.txt").write_text("line one\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.py").write_text("import os\n")
    set_working_dir(str(tmp_path))
    return tmp_path


class TestHandle:
    @pytest.mark.asyncio
    async def test_basic_glob(self, tmp_tree: Path) -> None:
        result = await handle(pattern="*.py", path=str(tmp_tree))
        assert result["count"] >= 1
        assert "hello.py" in result["files"]

    @pytest.mark.asyncio
    async def test_recursive_glob(self, tmp_tree: Path) -> None:
        result = await handle(pattern="**/*.py", path=str(tmp_tree))
        assert result["count"] >= 2
        files = result["files"]
        assert any("nested.py" in f for f in files)

    @pytest.mark.asyncio
    async def test_null_byte_in_pattern(self, tmp_tree: Path) -> None:
        result = await handle(pattern="*\x00*")
        assert "error" in result
        assert "null bytes" in result["error"]

    @pytest.mark.asyncio
    async def test_path_not_found(self, tmp_path: Path) -> None:
        result = await handle(pattern="*.py", path=str(tmp_path / "nonexistent"))
        assert "error" in result

    @pytest.mark.asyncio
    async def test_path_is_file_not_dir(self, tmp_tree: Path) -> None:
        result = await handle(pattern="*.py", path=str(tmp_tree / "hello.py"))
        assert "error" in result
        assert "not found" in result["error"].lower() or "Directory" in result["error"]

    @pytest.mark.asyncio
    async def test_default_working_dir(self, tmp_tree: Path) -> None:
        result = await handle(pattern="*.py")
        assert "files" in result
        assert result["count"] >= 1

    @pytest.mark.asyncio
    async def test_no_matches(self, tmp_tree: Path) -> None:
        result = await handle(pattern="*.xyz", path=str(tmp_tree))
        assert result["count"] == 0
        assert result["files"] == []
        assert result["truncated"] is False

    @pytest.mark.asyncio
    async def test_directories_excluded(self, tmp_tree: Path) -> None:
        result = await handle(pattern="*", path=str(tmp_tree))
        files = result["files"]
        assert "sub" not in files

    @pytest.mark.asyncio
    async def test_os_error_handled(self, tmp_tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def broken_glob(self: Path, pattern: str) -> list:
            raise OSError("Permission denied")

        monkeypatch.setattr(Path, "glob", broken_glob)
        result = await handle(pattern="*.py", path=str(tmp_tree))
        assert "error" in result
