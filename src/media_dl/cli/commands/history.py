"""History commands."""

from __future__ import annotations

import typer
from typing import Optional
from rich.console import Console
from rich.prompt import Confirm

from media_dl.config import get_settings
from media_dl.core.history import HistoryRepository
from media_dl.ui import (
    show_header,
    show_error_panel,
    show_success_panel,
    show_warning_panel,
    pause,
    get_console,
)
from media_dl.ui.tables import create_history_table, create_stats_table

app = typer.Typer(name="history", help="Ver y gestionar historial de descargas")


def _get_settings():
    return get_settings()


@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-l", help="Número de entradas a mostrar"),
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Filtrar por plataforma"),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Filtrar por tipo (video/audio)"),
    stats: bool = typer.Option(False, "--stats", "-s", help="Mostrar estadísticas"),
):
    """Ver historial de descargas"""
    settings = _get_settings()
    repo = HistoryRepository()

    show_header("📜 HISTORIAL DE DESCARGAS")

    if stats:
        stats_data = repo.get_stats()
        c = get_console()
        c.print(create_stats_table(stats_data))
        pause()
        return

    entries = repo.list(limit=limit, platform=platform, media_type=type)
    total = repo.count(platform=platform, media_type=type)

    if not entries:
        show_warning_panel("Historial Vacío", "No hay descargas registradas aún.")
        return

    c = get_console()
    c.print(f"[dim]Mostrando {len(entries)} de {total} entradas[/dim]")
    c.print(create_history_table(entries, limit))
    pause()


@app.command()
def clear(
    platform: Optional[str] = typer.Option(None, "--platform", "-p", help="Limpiar solo esta plataforma"),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Limpiar solo este tipo"),
    force: bool = typer.Option(False, "--force", "-f", help="No pedir confirmación"),
):
    """Limpiar historial"""
    settings = _get_settings()
    repo = HistoryRepository()

    show_header("🗑️ LIMPIAR HISTORIAL")

    if not force:
        filter_desc = []
        if platform:
            filter_desc.append(f"plataforma: {platform}")
        if type:
            filter_desc.append(f"tipo: {type}")

        filter_str = f" ({', '.join(filter_desc)})" if filter_desc else " (TODO)"
        if not Confirm.ask(f"[prompt]¿Eliminar todo el historial{filter_str}?[/prompt]", default=False):
            c = get_console()
            c.print("[yellow]Cancelado[/yellow]")
            return

    count = repo.clear(platform=platform, media_type=type)
    show_success_panel("✅ Historial Limpiado", f"Se eliminaron {count} registros")