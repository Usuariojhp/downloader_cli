"""Console singleton with cyan theme."""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

from media_dl.ui.theme import CYAN_THEME


_console_instance: Console | None = None


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