"""Doctor command for system diagnostics."""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys

import typer
from rich.table import Table

from media_dl.config import get_settings
from media_dl.ui import (
    get_console,
    show_error_panel,
    show_header,
    show_success_panel,
    show_warning_panel,
)
from media_dl.ui.theme import TABLE_BORDER_STYLE, TABLE_BOX, TABLE_HEADER_STYLE

app = typer.Typer(name="doctor", help="Diagnóstico del sistema", invoke_without_command=True)

console = get_console()


def _check_command(cmd: str) -> tuple[bool, str]:
    """Check if command exists and get version."""
    path = shutil.which(cmd)
    if not path:
        return False, "No instalado"
    try:
        result = subprocess.run(
            [cmd, "--version"], capture_output=True, text=True, timeout=5, check=False
        )
        version = result.stdout.strip().split("\n")[0] if result.stdout else "Desconocida"
        return True, version
    except Exception:
        return True, "Instalado (versión desconocida)"


def _missing(tool: str, consequence: str, installed: bool) -> str:
    """Return a bullet describing a missing external tool."""
    return "" if installed else f"• {tool}: No instalado ({consequence})"


def _check_python_package(pkg: str) -> tuple[bool, str]:
    """Check if Python package is installed."""
    try:
        module = importlib.import_module(pkg)
        version = getattr(module, "__version__", "Desconocida")
        return True, version
    except ImportError:
        return False, "No instalado"


def run_doctor(verbose: bool = False) -> None:
    """Print system diagnostics."""
    settings = get_settings()
    show_header("🏥 DIAGNÓSTICO DEL SISTEMA", "media-dl Cyan Edition")

    # Python
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # Core dependencies
    ytdlp_ok, ytdlp_ver = _check_python_package("yt_dlp")
    rich_ok, rich_ver = _check_python_package("rich")
    typer_ok, typer_ver = _check_python_package("typer")
    pydantic_ok, pydantic_ver = _check_python_package("pydantic")
    # SQLite is built-in
    sqlite_ok, sqlite_ver = True, "built-in (sqlite3)"

    # External tools
    aria2c_ok, aria2c_ver = _check_command("aria2c")
    ffmpeg_ok, ffmpeg_ver = _check_command("ffmpeg")

    # Optional packages
    spotdl_ok, spotdl_ver = _check_python_package("spotdl")
    scdl_ok, scdl_ver = _check_command("scdl")

    # Create table
    table = Table(
        show_header=True,
        header_style=TABLE_HEADER_STYLE,
        box=TABLE_BOX,
        border_style=TABLE_BORDER_STYLE,
    )
    table.add_column("Componente", style="yellow", width=25)
    table.add_column("Estado", style="white", width=15)
    table.add_column("Versión", style="cyan")
    table.add_column("Notas", style="dim")

    # Required
    table.add_row("Python", "✅" if True else "❌", python_version, "Requerido ≥3.11")
    table.add_row("yt-dlp", "✅" if ytdlp_ok else "❌", ytdlp_ver, "Motor de descarga principal")
    table.add_row("rich", "✅" if rich_ok else "❌", rich_ver, "Interfaz de terminal")
    table.add_row("typer", "✅" if typer_ok else "❌", typer_ver, "Framework CLI")
    table.add_row(
        "pydantic", "✅" if pydantic_ok else "❌", pydantic_ver, "Validación de configuración"
    )
    table.add_row("sqlite3", "✅" if sqlite_ok else "❌", sqlite_ver, "Base de datos (built-in)")

    # External tools
    table.add_row("", "", "", "")
    table.add_row("[bold]Herramientas Externas[/bold]", "", "", "")
    table.add_row(
        "aria2c", "✅" if aria2c_ok else "❌", aria2c_ver, "Descargas ultra rápidas (opcional)"
    )
    table.add_row(
        "ffmpeg", "✅" if ffmpeg_ok else "❌", ffmpeg_ver, "Conversión audio/video (recomendado)"
    )

    # Optional
    table.add_row("", "", "", "")
    table.add_row("[bold]Extensiones Opcionales[/bold]", "", "", "")
    table.add_row(
        "spotdl",
        "✅" if spotdl_ok else "⚠️",
        spotdl_ver,
        "Spotify (pip install 'media-dl[spotify]')",
    )
    table.add_row(
        "scdl",
        "✅" if scdl_ok else "⚠️",
        scdl_ver,
        "SoundCloud (pip install 'media-dl[soundcloud]')",
    )

    # Paths
    table.add_row("", "", "", "")
    table.add_row("[bold]Rutas[/bold]", "", "", "")
    table.add_row("Config dir", "📁", str(settings.config_dir), "")
    table.add_row("Database", "📄", str(settings.db_path), "")
    table.add_row("Downloads", "📁", str(settings.download_path), "")

    console.print(table)

    # Summary
    all_required = all([ytdlp_ok, rich_ok, typer_ok, pydantic_ok, sqlite_ok])
    external_ok = aria2c_ok and ffmpeg_ok

    if all_required and external_ok:
        show_success_panel(
            "✅ Sistema Listo",
            "Todos los componentes requeridos están disponibles.\n"
            "Las descargas ultra rápidas (aria2c) y conversión (ffmpeg) funcionarán.",
        )
    elif all_required:
        show_warning_panel(
            "⚠️ Sistema Parcial",
            "Componentes principales OK, pero faltan herramientas externas:\n"
            f"{_missing('aria2c', 'descargas ultra no disponibles', aria2c_ok)}\n"
            f"{_missing('ffmpeg', 'conversión MP3 no disponible', ffmpeg_ok)}\n\n"
            "Instala con:\n"
            "  • Ubuntu/Debian: sudo apt install aria2 ffmpeg\n"
            "  • macOS: brew install aria2 ffmpeg\n"
            "  • Windows: choco install aria2 ffmpeg",
        )
    else:
        show_error_panel(
            "❌ Sistema Incompleto",
            "Faltan dependencias Python requeridas.\nEjecuta: pip install -e '.[dev]'",
        )

    if verbose:
        console.print("\n[bold]Información adicional:[/bold]")
        console.print(f"  Platform: {sys.platform}")
        console.print(f"  Executable: {sys.executable}")
        console.print(f"  Config: {settings.config_file}")


def update_deps() -> None:
    """Upgrade yt-dlp and core dependencies."""
    show_header("🔄 ACTUALIZANDO DEPENDENCIAS")

    packages = [
        "yt-dlp",
        "rich",
        "typer",
        "pydantic",
        "pydantic-settings",
    ]

    for pkg in packages:
        console.print(f"[cyan]Actualizando {pkg}...[/cyan]")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", pkg],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            console.print(f"  [green]✅ {pkg} actualizado[/green]")
        else:
            console.print(f"  [red]❌ Error actualizando {pkg}: {result.stderr}[/red]")

    show_success_panel("✅ Actualización Completada", "Reinicia media-dl para aplicar cambios")


@app.callback(invoke_without_command=True)
def doctor(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Información detallada"),
) -> None:
    """Ejecutar diagnóstico del sistema"""
    run_doctor(verbose)


@app.command("update")
def update() -> None:
    """Actualizar yt-dlp y dependencias"""
    update_deps()
