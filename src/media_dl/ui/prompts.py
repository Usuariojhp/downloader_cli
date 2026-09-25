"""Validated input prompts for the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.prompt import Confirm, Prompt

from media_dl.core.exceptions import ValidationError
from media_dl.ui.console import get_console, is_interactive

console = get_console()


def _ask(prompt: str, default: str = "", **kwargs: Any) -> str:
    """Prompt for input, falling back to ``default`` when stdin is not a terminal."""
    if not is_interactive():
        return default
    try:
        return Prompt.ask(prompt, default=default, **kwargs)
    except (EOFError, KeyboardInterrupt):
        return default


def prompt_url(prompt_text: str = "URL del video/playlist") -> str:
    """Prompt for URL with basic validation."""
    while True:
        if not is_interactive():
            raise ValidationError(
                "Se requiere una terminal interactiva para introducir la URL", field="url"
            )
        url = _ask(f"[prompt]{prompt_text}[/prompt]").strip()
        if not url:
            console.print("[error]La URL no puede estar vacía[/error]")
            continue

        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            console.print("[error]La URL debe empezar con http:// o https://[/error]")
            continue

        return url


def prompt_urls_batch(
    prompt_text: str = "Pega las URLs (una por línea, línea vacía para terminar)",
) -> list[str]:
    """Prompt for multiple URLs."""
    urls = []
    console.print(f"[dim]{prompt_text}[/dim]")

    while True:
        url = _ask("[prompt]URL[/prompt]", default="").strip()
        if not url:
            break
        if url.startswith(("http://", "https://")):
            urls.append(url)
        else:
            console.print("[warning]URL ignorada (formato inválido): " + url[:50])

    return urls


def prompt_file_path(
    prompt_text: str,
    must_exist: bool = False,
    default: str = "",
) -> str:
    """Prompt for file path."""
    while True:
        path = _ask(f"[prompt]{prompt_text}[/prompt]", default=default).strip()
        if not path:
            if default:
                return default
            if not is_interactive():
                raise ValidationError(
                    "Se requiere una terminal interactiva para introducir la ruta", field="path"
                )
            console.print("[error]La ruta no puede estar vacía[/error]")
            continue

        path_obj = Path(path).expanduser()

        if must_exist and not path_obj.exists():
            console.print(f"[error]El archivo no existe: {path_obj}[/error]")
            continue

        return str(path_obj)


def prompt_directory(
    prompt_text: str,
    default: str = "",
    create: bool = True,
) -> str:
    """Prompt for directory path."""
    while True:
        path = _ask(f"[prompt]{prompt_text}[/prompt]", default=default).strip()
        if not path:
            if default:
                return default
            if not is_interactive():
                raise ValidationError(
                    "Se requiere una terminal interactiva para introducir la ruta", field="path"
                )
            console.print("[error]La ruta no puede estar vacía[/error]")
            continue

        path_obj = Path(path).expanduser()

        if path_obj.exists() and not path_obj.is_dir():
            console.print(f"[error]No es un directorio: {path_obj}[/error]")
            continue

        if create:
            path_obj.mkdir(parents=True, exist_ok=True)

        return str(path_obj)


def prompt_quality(available: list[str], default: str = "auto") -> str:
    """Ask which video quality to download.

    Acepta alturas con o sin la 'p' ("720" o "720p") y devuelve siempre el
    número sin sufijo, o "auto" para la mejor disponible.
    """
    qualities = [str(q).strip().rstrip("p") for q in available]
    marked = str(default).strip().rstrip("p")

    console.print("\n[bold cyan]📊 CALIDADES DISPONIBLES[/bold cyan]")

    for idx, q in enumerate(qualities, 1):
        marker = " [dim](actual)[/dim]" if q == marked else ""
        console.print(f"  {idx}. [cyan]{q}p[/cyan]{marker}")

    console.print(f"  {len(qualities) + 1}. [yellow]Mejor calidad automática[/yellow]")

    while True:
        choice = _ask(
            "[prompt]Elige calidad[/prompt]",
            default=str(len(qualities) + 1),
            choices=[str(i) for i in range(1, len(qualities) + 2)],
            show_choices=False,
        )

        idx = int(choice) - 1
        if idx < len(qualities):
            return qualities[idx]
        return "auto"


def prompt_audio_format(default: str = "mp3") -> str:
    """Ask for the audio format: original or MP3."""
    console.print("\n[bold cyan]🎵 FORMATO DE AUDIO[/bold cyan]")

    options = [
        ("original", "1", "Formato Original (Más rápido, sin recodificar)"),
        ("mp3", "2", "Convertir a MP3"),
    ]
    for value, number, label in options:
        marker = " [dim](actual)[/dim]" if value == default else ""
        colour = "green" if value == "original" else "yellow"
        console.print(f"  {number}. [{colour}]{label}[/{colour}]{marker}")

    fallback = "2" if default == "mp3" else "1"
    choice = _ask(
        "[prompt]Elige opción[/prompt]",
        default=fallback,
        choices=["1", "2"],
        show_choices=False,
    )
    return "original" if choice == "1" else "mp3"


def prompt_audio_bitrate(default: int = 192) -> int:
    """Ask for the MP3 bitrate."""
    console.print("\n[bold cyan]🎚️ CALIDAD MP3 (BITRATE)[/bold cyan]")

    options = [
        (320, "1", "Alta", "green"),
        (192, "2", "Media - Recomendado", "yellow"),
        (128, "3", "Baja", "red"),
    ]
    for value, number, label, colour in options:
        marker = " [dim](actual)[/dim]" if value == default else ""
        console.print(f"  {number}. [{colour}]{value} kbps · {label}[/{colour}]{marker}")

    fallback = {"320": "1", "192": "2", "128": "3"}.get(str(default), "2")
    choice = _ask(
        "[prompt]Elige calidad[/prompt]",
        default=fallback,
        choices=["1", "2", "3"],
        show_choices=False,
    )
    return {"1": 320, "2": 192, "3": 128}[choice]


def prompt_subtitle_languages(default: list[str] | None = None) -> list[str]:
    """Prompt for subtitle languages."""
    default = default or ["es", "en"]
    langs = _ask(
        "[prompt]Idiomas (separados por coma, ej: es,en,fr)[/prompt]",
        default=",".join(default),
    ).strip()

    return [lang.strip().lower() for lang in langs.split(",") if lang.strip()]


def prompt_playlist_range(total: int) -> str | None:
    """Prompt for playlist range selection."""
    console.print(f"\n[bold]Total videos: {total}[/bold]")
    console.print("[dim]Ejemplos: 1-5, 10, 15-20  |  'all' para todos[/dim]")

    range_input = (
        _ask(
            "[prompt]Rango a descargar[/prompt]",
            default="all",
        )
        .strip()
        .lower()
    )

    if range_input in ("all", "todo", "*", ""):
        return None

    # Validate range format
    try:
        parse_range(range_input, total)
        return range_input
    except ValueError as e:
        console.print(f"[error]{e}[/error]")
        return prompt_playlist_range(total)


def parse_range(range_str: str, max_val: int) -> list[int] | None:
    """Parse range string like '1-5,10,15-20' into list of indices (0-based).

    Returns None when the whole collection is selected ('all', 'todo', '*').
    """
    if range_str.strip().lower() in ("all", "todo", "*"):
        return None

    indices: list[int] = []

    for part in (raw.strip() for raw in range_str.split(",")):
        if not part:
            continue

        if "-" in part:
            start_raw, _, end_raw = part.partition("-")
            if not (start_raw.strip().isdigit() and end_raw.strip().isdigit()):
                raise ValueError(f"Formato de rango inválido: {part}")
            start_idx = int(start_raw) - 1
            end_idx = int(end_raw)
            if start_idx < 0 or end_idx > max_val or start_idx >= end_idx:
                raise ValueError(f"Formato de rango inválido: {part}")
            indices.extend(range(start_idx, end_idx))
        else:
            if not part.isdigit():
                raise ValueError(f"Índice inválido: {part}")
            idx = int(part) - 1
            if not 0 <= idx < max_val:
                raise ValueError(f"Índice inválido: {part}")
            indices.append(idx)

    # Remove duplicates and sort
    return sorted(set(indices))


def prompt_yes_no(prompt_text: str, default: bool = False) -> bool:
    """Prompt for yes/no confirmation."""
    if not is_interactive():
        return default
    try:
        return Confirm.ask(f"[prompt]{prompt_text}[/prompt]", default=default)
    except (EOFError, KeyboardInterrupt):
        return default


def prompt_int_range(
    prompt_text: str,
    min_val: int,
    max_val: int,
    default: int | None = None,
) -> int:
    """Prompt for integer within range."""
    while True:
        default_str = str(default) if default is not None else ""
        val = _ask(
            f"[prompt]{prompt_text}[/prompt]",
            default=default_str,
        ).strip()

        if not val and default is not None:
            return default

        try:
            num = int(val)
            if min_val <= num <= max_val:
                return num
            console.print(f"[error]Valor debe estar entre {min_val} y {max_val}[/error]")
        except ValueError:
            console.print("[error]Por favor ingresa un número válido[/error]")


def prompt_config_value(key: str, current: str, value_type: str = "string") -> str:
    """Prompt for configuration value with type validation."""
    type_hints = {
        "string": "",
        "int": " (número entero)",
        "bool": " (s/n)",
        "path": " (ruta de directorio)",
        "list": " (valores separados por coma)",
    }

    hint = type_hints.get(value_type, "")
    new_val = _ask(
        f"[prompt]{key}[/prompt]{hint} [dim](actual: {current})[/dim]",
        default=current,
    ).strip()

    if value_type == "int":
        try:
            int(new_val)
        except ValueError:
            console.print("[error]Debe ser un número entero[/error]")
            return prompt_config_value(key, current, value_type)

    elif value_type == "bool" and new_val.lower() not in (
        "s",
        "n",
        "si",
        "no",
        "yes",
        "true",
        "false",
    ):
        console.print("[error]Debe ser s/n o true/false[/error]")
        return prompt_config_value(key, current, value_type)

    return new_val
