"""Main entry point for media-dl."""

from __future__ import annotations

import sys
import typer
from rich.console import Console

from media_dl.config import get_settings, reset_settings
from media_dl.ui import get_console, show_header, show_error_panel
from media_dl.cli.commands import (
    download_app,
    playlist_app,
    history_app,
    config_app,
    doctor_app,
)

app = typer.Typer(
    name="media-dl",
    help="🚀 Unified Media Downloader - Cyan Edition",
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=True,
)

# Add subcommands
app.add_typer(download_app, name="download")
app.add_typer(playlist_app, name="playlist")
app.add_typer(history_app, name="history")
app.add_typer(config_app, name="config")
app.add_typer(doctor_app, name="doctor")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Mostrar versión"),
):
    """
    media-dl - Unified Media Downloader

    Descarga videos y audio de YouTube, TikTok, Instagram, Twitter, Facebook,
    Spotify, SoundCloud y muchas más plataformas.

    Características:
    • Descargas ultra rápidas con aria2c (16 conexiones paralelas)
    • Soporte para playlists y descargas por lotes
    • Historial SQLite con detección de duplicados
    • Configuración persistente
    • Tema cian moderno
    """
    if version:
        from media_dl import __version__
        console = get_console()
        console.print(f"[bold cyan]media-dl[/bold cyan] v{__version__}")
        raise typer.Exit()

    # Initialize settings on first run
    if ctx.invoked_subcommand is None:
        get_settings()
        show_header("🚀 media-dl", "Unified Media Downloader - Cyan Edition")
        console.print("[dim]Ejecuta 'media-dl --help' para ver comandos disponibles[/dim]")


@app.command()
def interactive():
    """Modo interactivo con menús"""
    from media_dl.ui import show_main_menu, prompt_yes_no, pause
    from media_dl.cli.commands.download import download_video, download_audio, download_batch
    from media_dl.cli.commands.playlist import playlist
    from media_dl.cli.commands.history import history, clear
    from media_dl.cli.commands.config import show, set, reset, path
    from media_dl.cli.commands.doctor import doctor

    settings = get_settings()
    console = get_console()

    while True:
        try:
            choice = show_main_menu()

            if choice == "1":
                url = typer.prompt("\n[prompt]📺 Pega la URL del VIDEO[/prompt]").strip()
                if url:
                    download_video.callback(url=url)

            elif choice == "2":
                url = typer.prompt("\n[prompt]🎵 Pega la URL del AUDIO[/prompt]").strip()
                if url:
                    download_audio.callback(url=url)

            elif choice == "3":
                download_batch.callback()

            elif choice == "4":
                history.callback()

            elif choice == "5":
                while True:
                    show_header("⚙️ CONFIGURACIÓN")
                    console.print("[bold]Opciones:[/bold]")
                    console.print("  1. Ver configuración")
                    console.print("  2. Cambiar valor")
                    console.print("  3. Restablecer por defecto")
                    console.print("  4. Ver rutas")
                    console.print("  0. Volver")

                    opt = typer.prompt("[prompt]Selecciona[/prompt]", type=int)
                    if opt == 1:
                        show.callback()
                    elif opt == 2:
                        key = typer.prompt("[prompt]Clave[/prompt]")
                        set.callback(key=key)
                    elif opt == 3:
                        reset.callback()
                    elif opt == 4:
                        path.callback()
                    elif opt == 0:
                        break

            elif choice == "6":
                doctor.callback()

            elif choice == "0":
                console.print("\n[bold green]👋 ¡Hasta luego![/bold green]")
                break

            if choice in ["1", "2", "3", "4"]:
                pause()

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️ Interrumpido por el usuario[/yellow]")
            if prompt_yes_no("¿Salir?", default=True):
                break
        except Exception as e:
            show_error_panel("Error", f"{type(e).__name__}: {e}")


def cli_main():
    """Entry point for console script."""
    try:
        app()
    except KeyboardInterrupt:
        console = get_console()
        console.print("\n[yellow]⚠️ Interrumpido[/yellow]")
        sys.exit(130)
    except Exception as e:
        console = get_console()
        show_error_panel("Error Crítico", f"{type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli_main()