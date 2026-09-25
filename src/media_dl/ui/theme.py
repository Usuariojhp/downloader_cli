"""Cyan theme definitions for Rich UI."""

from rich import box
from rich.style import Style
from rich.theme import Theme

CYAN_THEME = Theme(
    {
        # Base colors
        "primary": "cyan",
        "secondary": "bright_cyan",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "muted": "dim cyan",
        "accent": "magenta",
        "info": "blue",
        "highlight": "bold bright_cyan",
        "dim": "dim white",
        # Component styles
        "panel.border": "cyan",
        "panel.title": "bold cyan",
        "table.header": "bold cyan",
        "table.border": "cyan",
        "table.row": "white",
        "table.row.alt": "dim white",
        "progress.bar": "cyan",
        "progress.complete": "bright_cyan",
        "progress.pulse": "cyan",
        "prompt": "bold cyan",
        "prompt.default": "dim cyan",
        "input": "white",
        "link": "underline cyan",
    }
)

# Box styles
PANEL_BOX = box.DOUBLE
TABLE_BOX = box.ROUNDED
MENU_BOX = box.ROUNDED
PROGRESS_BOX = box.ROUNDED

# Style constants
STYLE_PRIMARY = Style(color="cyan", bold=True)
STYLE_SECONDARY = Style(color="bright_cyan")
STYLE_SUCCESS = Style(color="green", bold=True)
STYLE_WARNING = Style(color="yellow", bold=True)
STYLE_ERROR = Style(color="red", bold=True)
STYLE_MUTED = Style(color="cyan", dim=True)
STYLE_ACCENT = Style(color="magenta", bold=True)
STYLE_INFO = Style(color="blue")
STYLE_HIGHLIGHT = Style(color="bright_cyan", bold=True)
STYLE_DIM = Style(dim=True)

# Panel styles
PANEL_STYLE = "cyan"
PANEL_TITLE_STYLE = "bold cyan"

# Table styles
TABLE_HEADER_STYLE = "bold cyan"
TABLE_BORDER_STYLE = "cyan"

# Progress styles
PROGRESS_BAR_STYLE = "cyan"
PROGRESS_COMPLETE_STYLE = "bright_cyan"

# Prompt styles (used by prompts.py)
STYLE_PROMPT = Style(color="cyan", bold=True)
STYLE_ERROR = Style(color="red", bold=True)
STYLE_WARNING = Style(color="yellow", bold=True)
