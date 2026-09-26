"""Main entry point for media-dl."""

from __future__ import annotations

import sys

import typer

from media_dl.cli.commands import (
    config_app,
    doctor_app,
    download_app,
    history_app,
    playlist,
)
from media_dl.config import get_settings
from media_dl.ui import get_console, show_error_panel, show_header

app = typer.Typer(
    name="media-dl",
    help="🚀 Unified Media Downloader - Cyan Edition",
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=True,
)

console = get_console()

# Add subcommands
app.add_typer(download_app, name="download")
app.command("playlist")(playlist)
app.add_typer(history_app, name="history")
app.add_typer(config_app, name="config")
app.add_typer(doctor_app, name="doctor")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Mostrar versión"),
) -> None:
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

        console.print(f"[bold cyan]media-dl[/bold cyan] v{__version__}")
        raise typer.Exit

    # Initialize settings on first run
    if ctx.invoked_subcommand is None:
        get_settings()
        show_header("🚀 media-dl", "Unified Media Downloader - Cyan Edition")
        console.print("[dim]Ejecuta 'media-dl --help' para ver comandos disponibles[/dim]")


@app.command()
def interactive() -> None:
    """Modo interactivo con menús"""
    from media_dl.cli.commands.config import reset_config, set_config, show_config, show_paths
    from media_dl.cli.commands.doctor import run_doctor
    from media_dl.cli.commands.download import run_audio, run_batch, run_video
    from media_dl.cli.commands.history import show_history
    from media_dl.ui import pause, prompt_yes_no, show_main_menu

    settings = get_settings()

    while True:
        try:
            choice = show_main_menu()

            if choice == "1":
                url = typer.prompt("\n[prompt]📺 Pega la URL del VIDEO[/prompt]").strip()
                if url:
                    # quality=None → pregunta la calidad disponible
                    run_video(
                        url=url,
                        quality=None,
                        ultra=settings.download_mode == "ultra",
                    )

            elif choice == "2":
                url = typer.prompt("\n[prompt]🎵 Pega la URL del AUDIO[/prompt]").strip()
                if url:
                    # formato y bitrate None → pregunta ambos
                    run_audio(
                        url=url,
                        audio_format=None,
                        bitrate=None,
                        ultra=settings.download_mode == "ultra",
                    )

            elif choice == "3":
                run_batch(media_type="video", ultra=settings.download_mode == "ultra")

            elif choice == "4":
                show_history()

            elif choice == "5":
                from media_dl.cli.commands.config import VALID_KEYS

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
                        show_config()
                    elif opt == 2:
                        # Show valid keys as hints
                        keys_str = ", ".join(f"[cyan]{k}[/cyan]" for k in VALID_KEYS)
                        console.print(f"\n[dim]Claves válidas: {keys_str}[/dim]")
                        key = typer.prompt("[prompt]Clave[/prompt]").strip()
                        if key not in VALID_KEYS:
                            show_error_panel("Error", f"Clave inválida: {key}")
                            pause()
                            continue
                        set_config(key)
                    elif opt == 3:
                        reset_config()
                    elif opt == 4:
                        show_paths()
                    elif opt == 0:
                        break

            elif choice == "6":
                run_doctor()

            elif choice == "0":
                console.print("\n[bold green]👋 ¡Hasta luego![/bold green]")
                break

            if choice in ["1", "2", "3", "4"]:
                pause()

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️ Interrumpido por el usuario[/yellow]")
            if prompt_yes_no("¿Salir?", default=True):
                break
        except typer.Exit:
            continue
        except Exception as e:
            show_error_panel("Error", f"{type(e).__name__}: {e}")


def cli_main() -> None:
    """Entry point for console script."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Interrumpido[/yellow]")
        sys.exit(130)
    except Exception as e:
        show_error_panel("Error Crítico", f"{type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
