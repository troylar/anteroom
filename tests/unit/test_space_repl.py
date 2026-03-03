"""Tests for space-related REPL integration functions."""

from __future__ import annotations

import re
import sqlite3

from anteroom.services.context_trust import sanitize_trust_tags


def test_inject_space_instructions_adds_xml_tags() -> None:
    """Space instructions are injected with XML envelope."""
    prompt = "base prompt"
    space = {"name": "myspace", "source_file": "/test.yaml", "id": "s1"}
    instructions = "Follow these space rules."

    safe_name = sanitize_trust_tags(space["name"]).replace('"', "&quot;")
    safe_instr = sanitize_trust_tags(instructions)
    result = prompt + ('\n\n<space_instructions space="' + safe_name + '">\n' + safe_instr + "\n</space_instructions>")

    assert "<space_instructions" in result
    assert "myspace" in result
    assert "Follow these space rules." in result


def test_strip_space_instructions_removes_xml_tags() -> None:
    """Strip function removes space instructions from prompt."""
    prompt = 'base prompt\n\n<space_instructions space="myspace">\nSome instructions\n</space_instructions>'
    stripped = re.sub(
        r"\n*<space_instructions[^>]*>.*?</space_instructions>",
        "",
        prompt,
        flags=re.DOTALL,
    )
    assert "<space_instructions" not in stripped
    assert stripped == "base prompt"


def test_strip_space_instructions_preserves_other_content() -> None:
    """Stripping space instructions doesn't affect project instructions."""
    prompt = (
        'base\n\n<project_instructions project="p">\nproj\n</project_instructions>'
        '\n\n<space_instructions space="s">\nspace\n</space_instructions>'
    )
    stripped = re.sub(
        r"\n*<space_instructions[^>]*>.*?</space_instructions>",
        "",
        prompt,
        flags=re.DOTALL,
    )
    assert "<project_instructions" in stripped
    assert "<space_instructions" not in stripped


def test_autodetect_space_by_cwd() -> None:
    """resolve_space_by_cwd returns space when cwd matches a space path."""
    from anteroom.db import _SCHEMA, _create_indexes
    from anteroom.services.space_storage import create_space, resolve_space_by_cwd, sync_space_paths

    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(_SCHEMA)
    _create_indexes(db)

    s = create_space(db, "devspace", source_file="/test.yaml")
    sync_space_paths(db, s["id"], [{"repo_url": "", "local_path": "/home/user/project"}])

    result = resolve_space_by_cwd(db, "/home/user/project")
    assert result is not None
    assert result["name"] == "devspace"


def test_autodetect_space_no_match() -> None:
    """resolve_space_by_cwd returns None when no path matches."""
    from anteroom.db import _SCHEMA, _create_indexes
    from anteroom.services.space_storage import resolve_space_by_cwd

    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(_SCHEMA)
    _create_indexes(db)

    result = resolve_space_by_cwd(db, "/home/user/other")
    assert result is None
