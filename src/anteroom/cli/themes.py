"""CLI color theme system.

Provides semantic color slots for all CLI output. Every color in the renderer
and REPL is routed through ``CliTheme`` so that themes and ``NO_COLOR`` work
uniformly.

Internal parameter names and DB columns are unrelated to this module —
this is purely presentation-layer theming.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class CliTheme:
    """Semantic color slots for CLI output.

    Each field maps to a visual role. Renderer and REPL code reference these
    slots instead of hardcoded hex values or Rich named colors.
    """

    # -- Accents --
    accent: str = ""  # primary accent (prompt, headers, badges)
    secondary: str = ""  # secondary text (labels, AI role markers)
    accent_hover: str = ""  # lighter accent for focused/hover states

    # -- Text --
    text_light: str = ""  # primary body text
    text_secondary: str = ""  # lighter secondary content
    muted: str = ""  # secondary text (tool results, status)
    chrome: str = ""  # UI chrome (hints, separators, MCP info)

    # -- Status --
    success: str = ""  # success indicators, added lines
    error: str = ""  # error text, inline failures
    warning: str = ""  # token warnings, caution indicators
    danger: str = ""  # critical token count, dangerous operations

    # -- Backgrounds --
    bg_dark: str = ""  # dialog/menu backgrounds
    bg_darker: str = ""  # toolbar background
    bg_shadow: str = ""  # drop shadow, deep backgrounds
    bg_highlight: str = ""  # selected list item background
    bg_subtle: str = ""  # hints, separators background

    # -- Special --
    diff_add_bg: str = ""  # added-line highlight in diffs
    diff_remove_bg: str = ""  # removed-line highlight in diffs
    mcp_indicator: str = ""  # MCP server status color
    dir_display: str = ""  # directory path in toolbar
    toolbar_sep: str = ""  # toolbar separator
    logo_blue: str = ""  # logo accent color

    @classmethod
    def load(cls, name: str) -> CliTheme:
        """Load a built-in theme by name, falling back to midnight."""
        if os.environ.get("NO_COLOR"):
            return _NO_COLOR_THEME
        theme = _BUILTIN_THEMES.get(name)
        if theme is None:
            theme = _BUILTIN_THEMES["midnight"]
        return theme

    @classmethod
    def available(cls) -> list[str]:
        """Return names of all built-in themes."""
        return list(_BUILTIN_THEMES.keys())

    def ansi_fg(self, slot: str) -> str:
        """Return ANSI escape for a theme color slot, or empty if NO_COLOR.

        Converts ``#RRGGBB`` hex to ``\\033[38;2;R;G;Bm``.
        Returns empty string for empty slot values (NO_COLOR mode).
        """
        value = getattr(self, slot, "")
        if not value:
            return ""
        return _hex_to_ansi_fg(value)

    @property
    def ansi_reset(self) -> str:
        """ANSI reset sequence, empty when NO_COLOR."""
        if not self.accent:
            return ""
        return "\033[0m"


def _hex_to_ansi_fg(hex_color: str) -> str:
    """Convert #RRGGBB to \\033[38;2;R;G;Bm ANSI escape."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return ""
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m"


def _validate_theme(theme: CliTheme) -> bool:
    """Check that all color slots are populated (non-empty strings)."""
    return all(getattr(theme, f.name) for f in fields(theme))


# ---------------------------------------------------------------------------
# Built-in themes
# ---------------------------------------------------------------------------

_MIDNIGHT = CliTheme(
    accent="#C5A059",
    secondary="#94A3B8",
    accent_hover="#e0c070",
    text_light="#e0e0e0",
    text_secondary="#c0c0d0",
    muted="#8b8b8b",
    chrome="#6b7280",
    success="#22c55e",
    error="#CD6B6B",
    warning="#e8b830",
    danger="#e05050",
    bg_dark="#1a1a2e",
    bg_darker="#1e1e2e",
    bg_shadow="#0a0a15",
    bg_highlight="#2a2a3e",
    bg_subtle="#3a3a4e",
    diff_add_bg="#132a13",
    diff_remove_bg="#3d1418",
    mcp_indicator="#88a0b8",
    dir_display="#a0a8b8",
    toolbar_sep="#505868",
    logo_blue="#3B82F6",
)

_DAWN = CliTheme(
    accent="#B8860B",
    secondary="#6B7280",
    accent_hover="#DAA520",
    text_light="#1F2937",
    text_secondary="#374151",
    muted="#6B7280",
    chrome="#9CA3AF",
    success="#059669",
    error="#DC2626",
    warning="#D97706",
    danger="#B91C1C",
    bg_dark="#FEF3C7",
    bg_darker="#FFFBEB",
    bg_shadow="#F3E8C0",
    bg_highlight="#FDE68A",
    bg_subtle="#FEF9C3",
    diff_add_bg="#D1FAE5",
    diff_remove_bg="#FEE2E2",
    mcp_indicator="#2563EB",
    dir_display="#4B5563",
    toolbar_sep="#D1D5DB",
    logo_blue="#2563EB",
)

_HIGH_CONTRAST = CliTheme(
    accent="#FFFF00",
    secondary="#FFFFFF",
    accent_hover="#FFFF80",
    text_light="#FFFFFF",
    text_secondary="#E0E0E0",
    muted="#C0C0C0",
    chrome="#A0A0A0",
    success="#00FF00",
    error="#FF0000",
    warning="#FFA500",
    danger="#FF4040",
    bg_dark="#000000",
    bg_darker="#000000",
    bg_shadow="#000000",
    bg_highlight="#333333",
    bg_subtle="#1A1A1A",
    diff_add_bg="#003300",
    diff_remove_bg="#330000",
    mcp_indicator="#00BFFF",
    dir_display="#E0E0E0",
    toolbar_sep="#666666",
    logo_blue="#00BFFF",
)

# Accessible theme: CVD-safe palette (blue/orange instead of red/green).
# Based on IBM Design Language color-blind safe palette.
_ACCESSIBLE = CliTheme(
    accent="#FFB000",
    secondary="#94A3B8",
    accent_hover="#FFD060",
    text_light="#e0e0e0",
    text_secondary="#c0c0d0",
    muted="#8b8b8b",
    chrome="#6b7280",
    success="#648FFF",
    error="#DC267F",
    warning="#FFB000",
    danger="#FE6100",
    bg_dark="#1a1a2e",
    bg_darker="#1e1e2e",
    bg_shadow="#0a0a15",
    bg_highlight="#2a2a3e",
    bg_subtle="#3a3a4e",
    diff_add_bg="#0d1a3a",
    diff_remove_bg="#3a0d20",
    mcp_indicator="#648FFF",
    dir_display="#a0a8b8",
    toolbar_sep="#505868",
    logo_blue="#648FFF",
)

# NO_COLOR: all slots empty, ANSI helpers return empty strings.
_NO_COLOR_THEME = CliTheme()

_BUILTIN_THEMES: dict[str, CliTheme] = {
    "midnight": _MIDNIGHT,
    "dawn": _DAWN,
    "high-contrast": _HIGH_CONTRAST,
    "accessible": _ACCESSIBLE,
}
