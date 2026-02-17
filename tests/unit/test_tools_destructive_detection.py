from __future__ import annotations

import pytest

from anteroom.tools import _is_destructive_command, _normalize_command


@pytest.mark.parametrize(
    "cmd,expected",
    [
        ("rm -rf /", True),
        ("rm\t-rf /", True),
        ("  rm\n -rf /", True),
        ("rmdir /tmp/x", True),
        ("git reset --hard HEAD~1", True),
        ("git push --force", True),
        ("git push   -f", True),
        ("echo hi", False),
        ("/bin/rm -rf /", True),
    ],
)
def test_is_destructive_command(cmd: str, expected: bool) -> None:
    assert _is_destructive_command(cmd) is expected


def test_normalize_command_collapses_whitespace() -> None:
    assert _normalize_command("rm\t -rf\n/") == "rm -rf /"


def test_is_destructive_command_word_boundary() -> None:
    # Should not match 'rmdir' when inside a longer word
    assert _is_destructive_command("myrmdir /tmp") is False
