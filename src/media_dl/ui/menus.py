"""Interactive menus for the CLI."""

from __future__ import annotations

from typing import Any

from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from media_dl.ui.console import get_console, is_interactive
from media_dl.ui.theme import (
    MENU_BOX,
    PANEL_BOX,
    PANEL_STYLE,
)

console = get_console()


def _ask(prompt: str, default: str = "", **kwargs: Any) -> str:
    """Prompt for input, falling back to ``default`` when stdin is not a terminal."""
    if not is_interactive():
        return default
    try:
        return Prompt.ask(prompt, default=default, **kwargs)
    except (EOFError, KeyboardInterrupt):
        return default


def show_header(title: str, subtitle: str = "") -> None:
    """Show main header panel."""
    content = Text()
    content.append("  ", style="dim")
    content.append(title, style="bold cyan")
    if subtitle:
        content.append(f"\n  {subtitle}", style="dim cyan")

    panel = Panel(
        content,
        box=PANEL_BOX,
        border_style=PANEL_STYLE,
        title="[bold cyan]media-dl[/bold cyan]",
        title_align="left",
        padding=(1, 2),
    )
    console.print(panel)


def show_menu(
    title: str,
    options: list[tuple[str, str, str]],
    exit_option: str = "Salir",
) -> str:
    """
    Show interactive menu and return selected key.

    Args:
        title: Menu title
        options: List of (key, label, description)
        exit_option: Label for exit option

    Returns:
        Selected key or "0" for exit
    """
    table = Table(
        show_header=False,
        box=MENU_BOX,
        border_style="cyan",
        padding=(0, 1),
    )
    table.add_column("Key", style="bold green", width=4, justify="center")
    table.add_column("Label", style="white", min_width=20)
    table.add_column("Description", style="dim cyan")

    for key, label, desc in options:
        table.add_row(key, label, desc)

    table.add_row("0", f"[red]{exit_option}[/red]", "")

    panel = Panel(
        table,
        title=f"[bold cyan]{title}[/bold cyan]",
        border_style="cyan",
        box=MENU_BOX,
        padding=(1, 2),
    )
    console.print(panel)

    valid_keys = [opt[0] for opt in options] + ["0"]
    return _ask(
        "[prompt]Selecciona una opción[/prompt]",
        default="0",
        choices=valid_keys,
        show_choices=False,
    )


def show_main_menu() -> str:
    """Show main menu and return choice."""
    options = [
        ("1", "📹 Descargar Video", "Descargar video con selector de calidad"),
        ("2", "🎵 Descargar Audio", "Descargar audio (MP3 u original)"),
        ("3", "📋 Descarga por Lotes", "Múltiples URLs desde archivo o entrada"),
        ("4", "📜 Ver Historial", "Ver descargas previas con detalles"),
        ("5", "⚙️  Configuración", "Personalizar comportamiento"),
        ("6", "🩺  Diagnóstico", "Ver estado del sistema"),
    ]
    return show_menu("MENÚ PRINCIPAL", options)


def show_info_panel(title: str, content: str) -> None:
    """Show informational panel."""
    panel = Panel(
        escape(content),
        title=f"[bold cyan]{title}[/bold cyan]",
        border_style="cyan",
        box=PANEL_BOX,
        padding=(1, 2),
    )
    console.print(panel)


def show_error_panel(title: str, content: str) -> None:
    """Show error panel."""
    panel = Panel(
        escape(content),
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
        box=PANEL_BOX,
        padding=(1, 2),
    )
    console.print(panel)


def show_success_panel(title: str, content: str) -> None:
    """Show success panel."""
    panel = Panel(
        escape(content),
        title=f"[bold green]{title}[/bold green]",
        border_style="green",
        box=PANEL_BOX,
        padding=(1, 2),
    )
    console.print(panel)


def show_warning_panel(title: str, content: str) -> None:
    """Show warning panel."""
    panel = Panel(
        escape(content),
        title=f"[bold yellow]{title}[/bold yellow]",
        border_style="yellow",
        box=PANEL_BOX,
        padding=(1, 2),
    )
    console.print(panel)


def pause(message: str = "Presiona Enter para continuar...") -> None:
    """Pause execution waiting for Enter."""
    if not is_interactive():
        return
    _ask(f"[dim]{message}[/dim]", default="", show_default=False)
