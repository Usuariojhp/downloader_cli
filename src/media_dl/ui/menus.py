"""Interactive menus for the CLI."""

from __future__ import annotations

from typing import Any

from rich.panel import Panel
from rich.prompt import Confirm, Prompt
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


def show_quality_menu(qualities: list[str], default: str = "auto") -> str:
    """Show quality selection menu."""
    table = Table(
        show_header=False,
        box=MENU_BOX,
        border_style="cyan",
    )
    table.add_column("#", style="bold green", width=4, justify="center")
    table.add_column("Calidad", style="white")

    for idx, q in enumerate(qualities, 1):
        marker = " ←" if q == default else ""
        table.add_row(str(idx), f"[cyan]{q}p[/cyan]{marker}")

    table.add_row(str(len(qualities) + 1), "[yellow]Mejor calidad automática[/yellow]")

    panel = Panel(
        table,
        title="[bold cyan]📊 CALIDADES DISPONIBLES[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)

    return _ask(
        "[prompt]Elige calidad[/prompt]",
        default=str(len(qualities) + 1),
        choices=[str(i) for i in range(1, len(qualities) + 2)],
        show_choices=False,
    )


def show_audio_format_menu() -> str:
    """Show audio format selection."""
    options = [
        ("1", "🎵 Formato Original", "Más rápido, sin recodificar"),
        ("2", "🎵 Convertir a MP3", "Compatible con todos los reproductores"),
    ]
    return show_menu("FORMATO DE AUDIO", options, exit_option="Cancelar")


def show_audio_bitrate_menu() -> str:
    """Show MP3 bitrate selection."""
    options = [
        ("1", "🟢 320 kbps", "Alta calidad"),
        ("2", "🟡 192 kbps", "Calidad media (recomendado)"),
        ("3", "🔴 128 kbps", "Baja calidad, archivo pequeño"),
    ]
    return show_menu("CALIDAD MP3 (BITRATE)", options, exit_option="Cancelar")


def show_playlist_options(playlist_title: str, total_videos: int) -> str:
    """Show playlist download options."""
    content = Text()
    content.append(f"\n  📺 Título: {playlist_title}\n", style="white")
    content.append(f"  📊 Videos: {total_videos}\n", style="cyan")

    panel = Panel(
        content,
        title="[bold magenta]🎬 PLAYLIST DETECTADA[/bold magenta]",
        border_style="magenta",
        box=PANEL_BOX,
        padding=(1, 2),
    )
    console.print(panel)

    options = [
        ("1", "📥 Descargar TODO", f"Todos los {total_videos} videos"),
        ("2", "🎯 Rango específico", "Ej: 1-5, 10, 15-20"),
        ("3", "❌ Cancelar", "Volver al menú"),
    ]
    return show_menu("OPCIONES DE PLAYLIST", options)


def show_batch_input_menu() -> str:
    """Show batch input method selection."""
    options = [
        ("1", "📋 Pegar URLs", "Una por línea, línea vacía para terminar"),
        ("2", "📁 Archivo .txt", "Cargar URLs desde archivo"),
    ]
    return show_menu("MÉTODO DE ENTRADA", options)


def confirm_action(message: str, default: bool = False) -> bool:
    """Show confirmation prompt."""
    if not is_interactive():
        return default
    try:
        return Confirm.ask(f"[prompt]{message}[/prompt]", default=default)
    except (EOFError, KeyboardInterrupt):
        return default


def prompt_input(
    prompt: str,
    default: str = "",
    password: bool = False,
) -> str:
    """Prompt for text input."""
    if not is_interactive() and not default:
        return ""
    return _ask(
        f"[prompt]{prompt}[/prompt]",
        default=default,
        password=password,
    )


def prompt_int(
    prompt: str,
    default: int = 0,
    min_val: int = 0,
    max_val: int = 100,
) -> int:
    """Prompt for integer input with validation."""
    while True:
        try:
            val = _ask(
                f"[prompt]{prompt}[/prompt]",
                default=str(default),
            )
            num = int(val)
            if min_val <= num <= max_val:
                return num
            console.print(f"[error]Valor debe estar entre {min_val} y {max_val}[/error]")
        except ValueError:
            console.print("[error]Por favor ingresa un número válido[/error]")


def show_info_panel(title: str, content: str) -> None:
    """Show informational panel."""
    panel = Panel(
        content,
        title=f"[bold cyan]{title}[/bold cyan]",
        border_style="cyan",
        box=PANEL_BOX,
        padding=(1, 2),
    )
    console.print(panel)


def show_error_panel(title: str, content: str) -> None:
    """Show error panel."""
    panel = Panel(
        content,
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
        box=PANEL_BOX,
        padding=(1, 2),
    )
    console.print(panel)


def show_success_panel(title: str, content: str) -> None:
    """Show success panel."""
    panel = Panel(
        content,
        title=f"[bold green]{title}[/bold green]",
        border_style="green",
        box=PANEL_BOX,
        padding=(1, 2),
    )
    console.print(panel)


def show_warning_panel(title: str, content: str) -> None:
    """Show warning panel."""
    panel = Panel(
        content,
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
