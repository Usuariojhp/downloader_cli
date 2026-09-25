"""Console singleton with cyan theme."""

from __future__ import annotations

import sys

from rich.console import Console

from media_dl.ui.theme import CYAN_THEME

_console_instance: Console | None = None


def is_interactive() -> bool:
    """Return True only when stdin is attached to a real terminal."""
    stdin = sys.stdin
    if stdin is None:
        return False
    try:
        return bool(stdin.isatty())
    except (AttributeError, ValueError):
        return False


def get_console() -> Console:
    """Get or create the global console instance with cyan theme."""
    global _console_instance
    if _console_instance is None:
        _console_instance = Console(
            theme=CYAN_THEME,
            highlight=True,
            markup=True,
            emoji=True,
        )
    return _console_instance


def reset_console() -> None:
    """Reset console for testing."""
    global _console_instance
    _console_instance = None
