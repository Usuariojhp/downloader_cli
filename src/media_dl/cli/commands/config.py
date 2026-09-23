"""Config commands."""

from __future__ import annotations

import typer
from pathlib import Path
from typing import Optional

from media_dl.config import get_settings, Settings
from media_dl.core.history import HistoryRepository
from media_dl.ui import (
    show_header,
    show_error_panel,
    show_success_panel,
    show_warning_panel,
    pause,
    prompt_directory,
    prompt_yes_no,
    prompt_int_range,
    prompt_config_value,
    get_console,
)
from media_dl.ui.tables import create_config_table

app = typer.Typer(name="config", help="Configuración")


def _get_settings() -> Settings:
    return get_settings()


@app.command()
def show():
    """Mostrar configuración actual"""
    settings = _get_settings()
    show_header("⚙️ CONFIGURACIÓN ACTUAL")

    config_dict = settings.model_dump()
    c = get_console()
    c.print(create_config_table(config_dict))
    pause()


@app.command()
def set(
    key: str = typer.Argument(..., help="Clave a modificar"),
    value: Optional[str] = typer.Argument(None, help="Nuevo valor (interactivo si se omite)"),
):
    """Establecer valor de configuración"""
    settings = _get_settings()
    repo = HistoryRepository()

    # Valid keys
    valid_keys = {
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
    }

    if key not in valid_keys:
        show_error_panel("Error", f"Clave inválida: {key}\nClaves válidas: {', '.join(valid_keys.keys())}")
        raise typer.Exit(1)

    value_type, description = valid_keys[key]
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
            min_val = 4 if "connections" in key else (1 if "split" in key else (1 if "concurrent" in key else 1))
            max_val = 32 if "connections" in key or "split" in key else (8 if "concurrent" in key else 10)
            value = str(prompt_int_range(f"Nuevo {description}", min_val, max_val, int(current)))
        elif value_type == "bool":
            value = "true" if prompt_yes_no(f"¿Activar {description}?", current) else "false"
        elif value_type == "list":
            value = prompt_config_value(key, str(current), value_type)
        else:
            value = prompt_config_value(key, str(current), value_type)

    # Validate and set
    try:
        old_value = str(current)

        if value_type == "int":
            setattr(settings, key, int(value))
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

        settings.save_config()
        repo.log_settings_change(key, old_value, value)

        show_success_panel("✅ Configuración Actualizada", f"{key} = {value}")

    except Exception as e:
        show_error_panel("Error", f"No se pudo establecer {key}: {e}")
        raise typer.Exit(1)


@app.command()
def reset(
    force: bool = typer.Option(False, "--force", "-f", help="No pedir confirmación"),
):
    """Restablecer configuración por defecto"""
    settings = _get_settings()
    repo = HistoryRepository()

    show_header("🔄 RESTABLECER CONFIGURACIÓN")

    if not force:
        if not prompt_yes_no("¿Restablecer TODA la configuración a valores por defecto?", default=False):
            console.print("[yellow]Cancelado[/yellow]")
            return

    # Reset to defaults by creating new settings
    new_settings = Settings()
    for key in settings.model_fields:
        if key in new_settings.model_fields:
            old = getattr(settings, key)
            new = getattr(new_settings, key)
            if old != new:
                repo.log_settings_change(key, str(old), str(new))

    # Save new defaults
    new_settings.save_config()

    show_success_panel("✅ Configuración Restablecida", "Valores por defecto aplicados")
    pause()


@app.command()
def path():
    """Mostrar rutas de configuración"""
    settings = _get_settings()
    show_header("📁 RUTAS DE CONFIGURACIÓN")

    console.print(f"[cyan]Config directory:[/cyan] {settings.config_dir}")
    console.print(f"[cyan]Database:[/cyan] {settings.db_path}")
    console.print(f"[cyan]Config file:[/cyan] {settings.config_dir / 'config.json'}")
    console.print(f"[cyan]Downloads:[/cyan] {settings.download_path}")
    pause()