"""Tests for CLI theme system."""

from __future__ import annotations

import os
from dataclasses import fields
from unittest.mock import patch

import pytest

from anteroom.cli.themes import _BUILTIN_THEMES, CliTheme, _hex_to_ansi_fg, _validate_theme


class TestCliThemeLoad:
    def test_load_midnight(self) -> None:
        theme = CliTheme.load("midnight")
        assert theme.accent == "#C5A059"
        assert theme.success == "#22c55e"

    def test_load_dawn(self) -> None:
        theme = CliTheme.load("dawn")
        assert theme.accent == "#B8860B"

    def test_load_high_contrast(self) -> None:
        theme = CliTheme.load("high-contrast")
        assert theme.accent == "#FFFF00"

    def test_load_accessible(self) -> None:
        theme = CliTheme.load("accessible")
        assert theme.success == "#648FFF"
        assert theme.error == "#DC267F"

    def test_fallback_to_midnight_for_unknown(self) -> None:
        theme = CliTheme.load("nonexistent-theme")
        assert theme == CliTheme.load("midnight")

    def test_no_color_returns_theme_with_valid_colors(self) -> None:
        """NO_COLOR theme must have valid color slots so Rich markup doesn't crash.

        Rich Console strips colors when NO_COLOR is set; ANSI helpers check the
        env var directly.
        """
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            theme = CliTheme.load("midnight")
            # Slots must be non-empty for Rich markup safety
            assert theme.accent != ""
            assert theme.success != ""
            assert theme.error != ""
            assert theme.bg_dark != ""

    def test_no_color_empty_string_triggers(self) -> None:
        with patch.dict(os.environ, {"NO_COLOR": ""}):
            theme = CliTheme.load("midnight")
            # Empty string is falsy, so NO_COLOR="" should NOT trigger
            assert theme.accent != ""

    def test_available_returns_all_themes(self) -> None:
        names = CliTheme.available()
        assert "midnight" in names
        assert "dawn" in names
        assert "high-contrast" in names
        assert "accessible" in names
        assert len(names) == 4


class TestBuiltInThemesComplete:
    @pytest.mark.parametrize("name", list(_BUILTIN_THEMES.keys()))
    def test_all_slots_populated(self, name: str) -> None:
        theme = _BUILTIN_THEMES[name]
        assert _validate_theme(theme), f"Theme '{name}' has empty color slots"

    @pytest.mark.parametrize("name", list(_BUILTIN_THEMES.keys()))
    def test_all_slots_are_valid_hex(self, name: str) -> None:
        theme = _BUILTIN_THEMES[name]
        for f in fields(theme):
            value = getattr(theme, f.name)
            assert value.startswith("#"), f"Theme '{name}' slot '{f.name}' = '{value}' is not a hex color"
            assert len(value) == 7, f"Theme '{name}' slot '{f.name}' = '{value}' is not #RRGGBB format"


class TestHexToAnsiFg:
    def test_valid_hex(self) -> None:
        assert _hex_to_ansi_fg("#C5A059") == "\033[38;2;197;160;89m"

    def test_valid_hex_lowercase(self) -> None:
        assert _hex_to_ansi_fg("#c5a059") == "\033[38;2;197;160;89m"

    def test_black(self) -> None:
        assert _hex_to_ansi_fg("#000000") == "\033[38;2;0;0;0m"

    def test_white(self) -> None:
        assert _hex_to_ansi_fg("#FFFFFF") == "\033[38;2;255;255;255m"

    def test_invalid_length(self) -> None:
        assert _hex_to_ansi_fg("#FFF") == ""

    def test_no_hash(self) -> None:
        assert _hex_to_ansi_fg("C5A059") == "\033[38;2;197;160;89m"


class TestAnsiHelpers:
    def test_ansi_fg_returns_escape(self) -> None:
        theme = CliTheme.load("midnight")
        result = theme.ansi_fg("accent")
        assert result.startswith("\033[38;2;")
        assert result.endswith("m")

    def test_ansi_fg_empty_slot_returns_empty(self) -> None:
        theme = CliTheme()  # all empty
        assert theme.ansi_fg("accent") == ""

    def test_ansi_fg_unknown_slot_returns_empty(self) -> None:
        theme = CliTheme.load("midnight")
        assert theme.ansi_fg("nonexistent") == ""

    def test_ansi_reset_returns_reset(self) -> None:
        theme = CliTheme.load("midnight")
        assert theme.ansi_reset == "\033[0m"

    def test_ansi_reset_empty_on_no_color(self) -> None:
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            theme = CliTheme.load("midnight")
            assert theme.ansi_reset == ""


class TestNoColorTheme:
    def test_slots_have_valid_colors(self) -> None:
        """NO_COLOR theme keeps valid color values for Rich markup safety."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            theme = CliTheme.load("midnight")
            for f in fields(theme):
                value = getattr(theme, f.name)
                assert value != "", f"NO_COLOR theme slot '{f.name}' must not be empty (Rich markup crash)"

    def test_ansi_fg_returns_empty(self) -> None:
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            theme = CliTheme.load("midnight")
            assert theme.ansi_fg("accent") == ""

    def test_ansi_reset_returns_empty(self) -> None:
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            theme = CliTheme.load("midnight")
            assert theme.ansi_reset == ""

    def test_rich_markup_does_not_crash(self) -> None:
        """Verify that theme colors produce valid Rich markup even in NO_COLOR mode."""
        from io import StringIO

        from rich.console import Console

        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            theme = CliTheme.load("midnight")
            buf = StringIO()
            c = Console(file=buf, no_color=True)
            # These would raise MarkupError if colors were empty strings
            c.print(f"[{theme.success}]ok[/{theme.success}]")
            c.print(f"[{theme.error}]err[/{theme.error}]")
            c.print(f"[{theme.danger}]warn[/{theme.danger}]")
            output = buf.getvalue()
            assert "ok" in output
            assert "err" in output


class TestThemeImmutability:
    def test_frozen_dataclass(self) -> None:
        theme = CliTheme.load("midnight")
        with pytest.raises(AttributeError):
            theme.accent = "#000000"  # type: ignore[misc]


class TestValidateTheme:
    def test_valid_theme(self) -> None:
        assert _validate_theme(CliTheme.load("midnight")) is True

    def test_empty_theme_invalid(self) -> None:
        assert _validate_theme(CliTheme()) is False
