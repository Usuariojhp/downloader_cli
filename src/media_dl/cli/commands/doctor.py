"""Doctor command for system diagnostics."""

from __future__ import annotations

import contextlib
import importlib
import importlib.metadata
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
    """Check if Python package is installed and read its version.

    En el binario congelado importlib.metadata no encuentra nada, así que se
    prueba también el atributo del propio módulo y su sub-módulo .version
    (que es como yt-dlp expone la suya).
    """
    try:
        module = importlib.import_module(pkg)
    except ImportError:
        return False, "No instalado"

    version: str | None = getattr(module, "__version__", None)
    if not version:
        with contextlib.suppress(Exception):
            version = importlib.import_module(f"{pkg}.version").__version__
    if not version:
        with contextlib.suppress(Exception):
            version = importlib.metadata.version(pkg)
    return True, version or "Desconocida"


def _is_portable() -> bool:
    """True si estamos en el binario de PyInstaller, donde no vale hacer pip."""
    return bool(getattr(sys, "frozen", False))


def run_doctor(verbose: bool = False) -> bool:
    """Print system diagnostics. Devuelve False si algo opcional falta."""
    settings = get_settings()
    show_header("🏥 DIAGNÓSTICO DEL SISTEMA", "media-dl Cyan Edition")

    # Python
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # Core dependencies
    ytdlp_ok, ytdlp_ver = _check_python_package("yt_dlp")
    rich_ok, rich_ver = _check_python_package("rich")
    typer_ok, typer_ver = _check_python_package("typer")
    pydantic_ok, pydantic_ver = _check_python_package("pydantic")
    # mutagen no es solo para etiquetas: sin el no hay carátula, y como
    # embed_cover se traga la excepcion, se pierde en silencio. Ponerlo
    # aqui lo convierte en fallo visible de --strict.
    mutagen_ok, mutagen_ver = _check_python_package("mutagen.id3")
    # Import estatico a proposito: si se perdiera al empaquetar, el self_test
    # de abajo lo cuenta y el --strict de la CI pone el build en rojo.
    from media_dl.core.cover import ca_status
    from media_dl.core.cover import self_test as cover_self_test

    cover_ok, cover_reason = cover_self_test()
    ca_ok, ca_reason = ca_status()
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
    table.add_row("mutagen", "✅" if mutagen_ok else "❌", mutagen_ver, "Carátulas incrustadas")
    table.add_row(
        "Portada (self-test)",
        "✅" if cover_ok else "❌",
        cover_reason,
        "Prueba real de escritura, sin red",
    )
    table.add_row(
        "Certificados TLS",
        "✅" if ca_ok else "❌",
        ca_reason,
        "Fuente de CA disponible para urllib",
    )

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
    portable = _is_portable()
    spotify_hint = (
        "Spotify: no incluido en este binario"
        if portable
        else "Spotify (pip install 'media-dl[spotify]')"
    )
    soundcloud_hint = (
        "SoundCloud: no incluido en este binario"
        if portable
        else "SoundCloud (pip install 'media-dl[soundcloud]')"
    )
    table.add_row("", "", "", "")
    table.add_row("[bold]Extensiones Opcionales[/bold]", "", "", "")
    table.add_row("spotdl", "✅" if spotdl_ok else "⚠️", spotdl_ver, spotify_hint)
    table.add_row("scdl", "✅" if scdl_ok else "⚠️", scdl_ver, soundcloud_hint)

    # Paths
    table.add_row("", "", "", "")
    table.add_row("[bold]Rutas[/bold]", "", "", "")
    table.add_row("Config dir", "📁", str(settings.config_dir), "")
    table.add_row("Database", "📄", str(settings.db_path), "")
    table.add_row("Downloads", "📁", str(settings.download_path), "")

    console.print(table)

    # Summary
    all_required = all(
        [ytdlp_ok, rich_ok, typer_ok, pydantic_ok, sqlite_ok, mutagen_ok, cover_ok, ca_ok]
    )
    external_ok = aria2c_ok and ffmpeg_ok

    # Una extensión opcional rota no impide usar el programa, pero en el
    # binario significa que el spec la ha dejado fuera: hay que decirlo en
    # vez de celebrar un "Sistema Listo" que luego no descarga de Spotify.
    broken_extras = [
        name
        for name, ok in (
            ("spotdl (Spotify)", spotdl_ok),
            ("scdl (SoundCloud)", scdl_ok),
        )
        if not ok
    ]
    extra_note = ""
    if broken_extras:
        extra_note = (
            f"\n\nExtensiones que NO funcionan: {', '.join(broken_extras)}. "
            "Las demás descargas no se ven afectadas."
        )

    if all_required and external_ok and not broken_extras:
        show_success_panel(
            "✅ Sistema Listo",
            "Todos los componentes requeridos están disponibles.\n"
            "Las descargas ultra rápidas (aria2c) y conversión (ffmpeg) funcionarán.",
        )
    elif all_required and not broken_extras:
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
    elif all_required:
        show_warning_panel(
            "✅ Sistema Listo, pero sin algunas extensiones",
            f"Lo esencial funciona: descargar, convertir y guardar en el historial.{extra_note}",
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

    # --strict solo juzga lo que el paquete y el spec pueden arreglar: las
    # dependencias de Python y las extensiones que el binario declara traer.
    # ffmpeg y aria2c son programas del sistema, no se pueden empaquetar, y su
    # ausencia ya avisa en el panel de arriba. Si tambien fallaran aqui,
    # cualquier runner de CI sin ffmpeg pondria el build en rojo por algo que
    # no es un defecto del artefacto, y dejaria de comprobar lo que si importa.
    return not (broken_extras or not all_required)


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
    strict: bool = typer.Option(
        False,
        "--strict",
        help=(
            "Sale con error si falta una dependencia o una extensión incluida. "
            "No cuenta ffmpeg/aria2c, que son del sistema"
        ),
    ),
) -> None:
    """Ejecutar diagnóstico del sistema"""
    healthy = run_doctor(verbose)
    if strict and not healthy:
        raise typer.Exit(1)


@app.command("update")
def update() -> None:
    """Actualizar yt-dlp y dependencias"""
    update_deps()
