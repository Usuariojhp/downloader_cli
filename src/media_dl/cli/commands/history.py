"""History commands."""

from __future__ import annotations

import typer
from rich.prompt import Confirm

from media_dl.config import get_settings
from media_dl.core.history import HistoryRepository
from media_dl.ui import (
    get_console,
    pause,
    show_header,
    show_success_panel,
    show_warning_panel,
)
from media_dl.ui.tables import create_history_table, create_stats_table

app = typer.Typer(name="history", help="Ver y gestionar historial de descargas")

console = get_console()


def show_history(
    limit: int = 20,
    platform: str | None = None,
    media_type: str | None = None,
    stats: bool = False,
) -> None:
    """Show download history or statistics."""
    get_settings()
    repo = HistoryRepository()

    show_header("📜 HISTORIAL DE DESCARGAS")

    if stats:
        console.print(create_stats_table(repo.get_stats()))
        pause()
        return

    entries = repo.list(limit=limit, platform=platform, media_type=media_type)
    total = repo.count(platform=platform, media_type=media_type)

    if not entries:
        show_warning_panel("Historial Vacío", "No hay descargas registradas aún.")
        return

    console.print(f"[dim]Mostrando {len(entries)} de {total} entradas[/dim]")
    console.print(create_history_table(entries, limit))
    pause()


def clear_history(
    platform: str | None = None,
    media_type: str | None = None,
    force: bool = False,
) -> None:
    """Delete history records, optionally filtered."""
    get_settings()
    repo = HistoryRepository()

    show_header("🗑️ LIMPIAR HISTORIAL")

    if not force:
        filter_desc = []
        if platform:
            filter_desc.append(f"plataforma: {platform}")
        if media_type:
            filter_desc.append(f"tipo: {media_type}")

        filter_str = f" ({', '.join(filter_desc)})" if filter_desc else " (TODO)"
        if not Confirm.ask(
            f"[prompt]¿Eliminar todo el historial{filter_str}?[/prompt]", default=False
        ):
            console.print("[yellow]Cancelado[/yellow]")
            return

    count = repo.clear(platform=platform, media_type=media_type)
    show_success_panel("✅ Historial Limpiado", f"Se eliminaron {count} registros")


@app.callback(invoke_without_command=True)
def history_default(
    ctx: typer.Context,
    limit: int = typer.Option(20, "--limit", "-l", help="Número de entradas a mostrar"),
    platform: str | None = typer.Option(None, "--platform", "-p", help="Filtrar por plataforma"),
    type: str | None = typer.Option(None, "--type", "-t", help="Filtrar por tipo (video/audio)"),
    stats: bool = typer.Option(False, "--stats", "-s", help="Mostrar estadísticas"),
) -> None:
    """Ver historial de descargas"""
    if ctx.invoked_subcommand is None:
        show_history(limit=limit, platform=platform, media_type=type, stats=stats)


@app.command("clear")
def clear(
    platform: str | None = typer.Option(
        None, "--platform", "-p", help="Limpiar solo esta plataforma"
    ),
    type: str | None = typer.Option(None, "--type", "-t", help="Limpiar solo este tipo"),
    force: bool = typer.Option(False, "--force", "-f", help="No pedir confirmación"),
) -> None:
    """Limpiar historial"""
    clear_history(platform=platform, media_type=type, force=force)
