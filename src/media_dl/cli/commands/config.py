"""Config commands."""

from __future__ import annotations

from pathlib import Path

import typer

from media_dl.config import Settings, get_settings
from media_dl.core.history import HistoryRepository
from media_dl.ui import (
    get_console,
    pause,
    prompt_config_value,
    prompt_directory,
    prompt_int_range,
    prompt_yes_no,
    show_error_panel,
    show_header,
    show_success_panel,
)
from media_dl.ui.tables import create_config_table

app = typer.Typer(name="config", help="Configuración")

console = get_console()

VALID_KEYS = {
    "download_path": ("path", "Carpeta de descargas"),
    "download_mode": ("choice", "Modo de descarga (ultra/normal)"),
    "default_video_quality": ("string", "Calidad video por defecto"),
    "default_audio_format": ("choice", "Formato audio (original/mp3)"),
    "default_audio_bitrate": ("int", "Bitrate audio (128/192/320)"),
    "auto_subtitle": ("bool", "Subtítulos automáticos"),
    "subtitle_languages": ("list", "Idiomas subtítulos (coma separados)"),
    "retry_attempts": ("int", "Intentos de reintento (1-10)"),
    "check_duplicates": ("bool", "Verificar duplicados"),
    "aria2c_connections": ("int", "Conexiones Aria2c (4-32)"),
    "aria2c_split": ("int", "Split Aria2c (1-32)"),
    "max_download_speed": ("int", "Límite velocidad KB/s (0=sin límite)"),
    "concurrent_downloads": ("int", "Descargas concurrentes (1-8)"),
    "embed_thumbnail": ("bool", "Insertar miniatura"),
    "embed_metadata": ("bool", "Insertar metadatos"),
    "write_info_json": ("bool", "Escribir info.json"),
    "spotify_client_id": ("string", "Spotify Client ID (opcional, mejores límites)"),
    "spotify_client_secret": ("string", "Spotify Client Secret (opcional)"),
}

INT_RANGES = {
    "default_audio_bitrate": (128, 320),
    "retry_attempts": (1, 10),
    "aria2c_connections": (4, 32),
    "aria2c_split": (1, 32),
    "max_download_speed": (0, 1_000_000),
    "concurrent_downloads": (1, 8),
}


def _get_settings() -> Settings:
    return get_settings()


def show_config() -> None:
    """Print the current configuration."""
    settings = _get_settings()
    show_header("⚙️ CONFIGURACIÓN ACTUAL")

    config_dict = settings.model_dump()
    c = get_console()
    c.print(create_config_table(config_dict))
    console.print(f"[dim]Archivo: {settings.config_file}[/dim]")
    pause()


def set_config(key: str, value: str | None = None) -> None:
    """Set a configuration value (interactive when value is None)."""
    settings = _get_settings()
    repo = HistoryRepository()

    if key not in VALID_KEYS:
        show_error_panel(
            "Error", f"Clave inválida: {key}\nClaves válidas: {', '.join(VALID_KEYS.keys())}"
        )
        raise typer.Exit(1)

    value_type, description = VALID_KEYS[key]
    current = getattr(settings, key)

    if value is None:
        # Interactive
        if value_type == "choice":
            if key == "download_mode":
                console.print("\n1. ultra (Aria2c)")
                console.print("2. normal")
                choice = typer.prompt("Elige modo", type=int)
                value = "ultra" if choice == 1 else "normal"
            elif key == "default_audio_format":
                console.print("\n1. original")
                console.print("2. mp3")
                choice = typer.prompt("Elige formato", type=int)
                value = "original" if choice == 1 else "mp3"
            else:
                value = prompt_config_value(key, str(current), value_type)
        elif value_type == "path":
            value = prompt_directory(f"Nueva {description}", default=str(current))
        elif value_type == "int":
            min_val, max_val = INT_RANGES.get(key, (1, 1000))
            value = str(prompt_int_range(f"Nuevo {description}", min_val, max_val, int(current)))
        elif value_type == "bool":
            value = "true" if prompt_yes_no(f"¿Activar {description}?", current) else "false"
        else:
            value = prompt_config_value(key, str(current), value_type)

    # Validate and set
    try:
        old_value = str(current)

        if value_type == "int":
            number = int(value)
            bounds = INT_RANGES.get(key)
            if bounds is not None and not bounds[0] <= number <= bounds[1]:
                raise ValueError(f"el valor debe estar entre {bounds[0]} y {bounds[1]}")
            setattr(settings, key, number)
        elif value_type == "bool":
            setattr(settings, key, value.lower() in ("true", "1", "yes", "s", "si"))
        elif value_type == "list":
            setattr(settings, key, [v.strip() for v in value.split(",") if v.strip()])
        elif value_type == "path":
            path = Path(value).expanduser()
            path.mkdir(parents=True, exist_ok=True)
            setattr(settings, key, path)
        else:
            setattr(settings, key, value)

        config_path = settings.save_config()
        repo.log_settings_change(key, old_value, value)

        display_value = "***" if "secret" in key.lower() else value
        show_success_panel(
            "✅ Configuración Actualizada", f"{key} = {display_value}\nGuardado en {config_path}"
        )

    except Exception as e:
        show_error_panel("Error", f"No se pudo establecer {key}: {e}")
        raise typer.Exit(1) from e


def reset_config(force: bool = False) -> None:
    """Restore factory defaults for user preferences."""
    settings = _get_settings()
    repo = HistoryRepository()

    show_header("🔄 RESTABLECER CONFIGURACIÓN")

    if not force and not prompt_yes_no(
        "¿Restablecer TODA la configuración a valores por defecto?", default=False
    ):
        console.print("[yellow]Cancelado[/yellow]")
        return

    # Reset user preferences to factory defaults (runtime paths are preserved)
    new_settings = Settings.defaults()
    for key in settings.to_config_dict():
        old = getattr(settings, key)
        new = getattr(new_settings, key)
        if old != new:
            repo.log_settings_change(key, str(old), str(new))
            setattr(settings, key, new)

    config_path = settings.save_config()

    show_success_panel(
        "✅ Configuración Restablecida", f"Valores por defecto guardados en {config_path}"
    )
    pause()


def show_paths() -> None:
    """Print configuration paths."""
    settings = _get_settings()
    show_header("📁 RUTAS DE CONFIGURACIÓN")

    console.print(f"[cyan]Config directory:[/cyan] {settings.config_dir}")
    console.print(f"[cyan]Database:[/cyan] {settings.db_path}")
    console.print(f"[cyan]Config file:[/cyan] {settings.config_dir / 'config.json'}")
    console.print(f"[cyan]Downloads:[/cyan] {settings.download_path}")
    pause()


@app.command("show")
def show() -> None:
    """Mostrar configuración actual"""
    show_config()


@app.command("set")
def set(
    key: str = typer.Argument(..., help="Clave a modificar"),
    value: str | None = typer.Argument(None, help="Nuevo valor (interactivo si se omite)"),
) -> None:
    """Establecer valor de configuración"""
    set_config(key, value)


@app.command("reset")
def reset(
    force: bool = typer.Option(False, "--force", "-f", help="No pedir confirmación"),
) -> None:
    """Restablecer configuración por defecto"""
    reset_config(force)


@app.command("path")
def path() -> None:
    """Mostrar rutas de configuración"""
    show_paths()
