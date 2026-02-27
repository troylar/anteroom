"""Tests for artifact health check CLI subcommand."""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from anteroom.db import _SCHEMA, ThreadSafeConnection
from anteroom.services import artifact_storage


@pytest.fixture()
def db() -> ThreadSafeConnection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    conn.commit()
    return ThreadSafeConnection(conn)


def _create(db: ThreadSafeConnection, fqn: str, content: str, source: str = "local") -> dict:
    ns, atype, name = fqn[1:].split("/", 2)
    return artifact_storage.create_artifact(db, fqn, atype, ns, name, content, source=source)


def _make_args(**kwargs: object) -> MagicMock:
    args = MagicMock()
    args.artifact_action = "check"
    args.json_output = False
    args.fix = False
    args.project = False
    for k, v in kwargs.items():
        setattr(args, k, v)
    return args


def _make_config() -> MagicMock:
    config = MagicMock()
    config.app.data_dir.__truediv__ = MagicMock(return_value="/tmp/test.db")
    return config


class TestArtifactCheckCli:
    def test_check_healthy_db(self, db: ThreadSafeConnection, capsys: pytest.CaptureFixture[str]) -> None:
        from rich.console import Console

        from anteroom.__main__ import _run_artifact_check

        console = Console(force_terminal=False, no_color=True)
        args = _make_args()
        _run_artifact_check(_make_config(), args, db, console)
        captured = capsys.readouterr()
        assert "No issues found" in captured.out

    def test_check_with_issues(self, db: ThreadSafeConnection, capsys: pytest.CaptureFixture[str]) -> None:
        from rich.console import Console

        from anteroom.__main__ import _run_artifact_check

        _create(db, "@team/config_overlay/a", "key: val1\n", source="team")
        _create(db, "@local/config_overlay/b", "key: val2\n", source="local")
        console = Console(force_terminal=False, no_color=True)
        args = _make_args()
        _run_artifact_check(_make_config(), args, db, console)
        captured = capsys.readouterr()
        assert "Artifact Health Check" in captured.out
        assert "error" in captured.out.lower() or "conflict" in captured.out.lower()

    def test_json_output(self, db: ThreadSafeConnection, capsys: pytest.CaptureFixture[str]) -> None:
        from rich.console import Console

        from anteroom.__main__ import _run_artifact_check

        _create(db, "@core/skill/a", "Some skill content with enough words to pass checks")
        console = Console(force_terminal=False, no_color=True)
        args = _make_args(json_output=True)
        _run_artifact_check(_make_config(), args, db, console)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "healthy" in data
        assert "artifact_count" in data
        assert "issues" in data
        assert data["artifact_count"] == 1

    def test_fix_flag(self, db: ThreadSafeConnection, capsys: pytest.CaptureFixture[str]) -> None:
        from rich.console import Console

        from anteroom.__main__ import _run_artifact_check

        _create(db, "@a/rule/dup", "Same content", source="team")
        _create(db, "@b/rule/dup", "Same content", source="local")
        console = Console(force_terminal=False, no_color=True)
        args = _make_args(fix=True)
        _run_artifact_check(_make_config(), args, db, console)
        remaining = artifact_storage.list_artifacts(db)
        assert len(remaining) == 1

    def test_action_routing(self, db: ThreadSafeConnection, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify the check action is dispatched from _run_artifact."""
        from anteroom.__main__ import _run_artifact

        config = _make_config()
        args = _make_args()
        with patch("anteroom.db.get_db", return_value=db):
            _run_artifact(config, args)
        captured = capsys.readouterr()
        assert "Health Check" in captured.out or "No issues" in captured.out

    def test_empty_action_shows_usage(self, capsys: pytest.CaptureFixture[str]) -> None:
        from anteroom.__main__ import _run_artifact

        config = _make_config()
        args = MagicMock()
        args.artifact_action = None
        _run_artifact(config, args)
        captured = capsys.readouterr()
        assert "check" in captured.out
