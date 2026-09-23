"""Validated input prompts for the CLI."""

from __future__ import annotations

from typing import Optional, List
from pathlib import Path
from rich.prompt import Prompt, Confirm
from rich.console import Console

from media_dl.ui.console import get_console
from media_dl.ui.theme import STYLE_PROMPT, STYLE_ERROR
from media_dl.core.exceptions import ValidationError


console = get_console()


def prompt_url(prompt_text: str = "URL del video/playlist") -> str:
    """Prompt for URL with basic validation."""
    while True:
        url = Prompt.ask(f"[prompt]{prompt_text}[/prompt]").strip()
        if not url:
            console.print("[error]La URL no puede estar vacía[/error]")
            continue

        # Basic URL validation
        if not (url.startswith("http://") or url.startswith("https://")):
            console.print("[error]La URL debe empezar con http:// o https://[/error]")
            continue

        return url


def prompt_urls_batch(prompt_text: str = "Pega las URLs (una por línea, línea vacía para terminar)") -> List[str]:
    """Prompt for multiple URLs."""
    urls = []
    console.print(f"[dim]{prompt_text}[/dim]")

    while True:
        url = Prompt.ask("[prompt]URL[/prompt]", default="").strip()
        if not url:
            break
        if url.startswith("http://") or url.startswith("https://"):
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
        path = Prompt.ask(f"[prompt]{prompt_text}[/prompt]", default=default).strip()
        if not path:
            if default:
                return default
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
        path = Prompt.ask(f"[prompt]{prompt_text}[/prompt]", default=default).strip()
        if not path:
            if default:
                return default
            console.print("[error]La ruta no puede estar vacía[/error]")
            continue

        path_obj = Path(path).expanduser()

        if path_obj.exists() and not path_obj.is_dir():
            console.print(f"[error]No es un directorio: {path_obj}[/error]")
            continue

        if create:
            path_obj.mkdir(parents=True, exist_ok=True)

        return str(path_obj)


def prompt_quality(available: List[str], default: str = "auto") -> str:
    """Prompt for video quality selection."""
    console.print("\n[bold cyan]📊 CALIDADES DISPONIBLES[/bold cyan]")

    for idx, q in enumerate(available, 1):
        marker = " ← [dim](actual)[/dim]" if q == default else ""
        console.print(f"  {idx}. [cyan]{q}p[/cyan]{marker}")

    console.print(f"  {len(available) + 1}. [yellow]Mejor calidad automática[/yellow]")

    while True:
        choice = Prompt.ask(
            "[prompt]Elige calidad[/prompt]",
            choices=[str(i) for i in range(1, len(available) + 2)],
            show_choices=False,
        )

        idx = int(choice) - 1
        if idx < len(available):
            return available[idx]
        return "auto"


def prompt_audio_format() -> str:
    """Prompt for audio format."""
    console.print("\n[bold cyan]🎵 FORMATO DE AUDIO[/bold cyan]")
    console.print("  1. [green]Formato Original[/green] (Más rápido, sin recodificar)")
    console.print("  2. [yellow]Convertir a MP3[/yellow]")

    choice = Prompt.ask(
        "[prompt]Elige opción[/prompt]",
        choices=["1", "2"],
        show_choices=False,
    )
    return "original" if choice == "1" else "mp3"


def prompt_audio_bitrate() -> int:
    """Prompt for MP3 bitrate."""
    console.print("\n[bold cyan]🎚️ CALIDAD MP3 (BITRATE)[/bold cyan]")
    console.print("  1. [green]320 kbps[/green] (Alta)")
    console.print("  2. [yellow]192 kbps[/yellow] (Media - Recomendado)")
    console.print("  3. [red]128 kbps[/red] (Baja)")

    choice = Prompt.ask(
        "[prompt]Elige calidad[/prompt]",
        choices=["1", "2", "3"],
        show_choices=False,
    )
    return {"1": 320, "2": 192, "3": 128}[choice]


def prompt_subtitle_languages(default: List[str] = None) -> List[str]:
    """Prompt for subtitle languages."""
    default = default or ["es", "en"]
    langs = Prompt.ask(
        "[prompt]Idiomas (separados por coma, ej: es,en,fr)[/prompt]",
        default=",".join(default),
    ).strip()

    return [l.strip().lower() for l in langs.split(",") if l.strip()]


def prompt_playlist_range(total: int) -> Optional[str]:
    """Prompt for playlist range selection."""
    console.print(f"\n[bold]Total videos: {total}[/bold]")
    console.print("[dim]Ejemplos: 1-5, 10, 15-20  |  'all' para todos[/dim]")

    range_input = Prompt.ask(
        "[prompt]Rango a descargar[/prompt]",
        default="all",
    ).strip().lower()

    if range_input in ("all", "todo", "*", ""):
        return None

    # Validate range format
    try:
        parse_range(range_input, total)
        return range_input
    except ValueError as e:
        console.print(f"[error]{e}[/error]")
        return prompt_playlist_range(total)


def parse_range(range_str: str, max_val: int) -> List[int]:
    """Parse range string like '1-5,10,15-20' into list of indices (0-based)."""
    indices = []
    parts = range_str.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            try:
                start, end = part.split("-", 1)
                start_idx = int(start.strip()) - 1
                end_idx = int(end.strip())
                if start_idx < 0 or end_idx > max_val or start_idx >= end_idx:
                    raise ValueError(f"Rango inválido: {part}")
                indices.extend(range(start_idx, end_idx))
            except ValueError:
                raise ValueError(f"Formato de rango inválido: {part}")
        else:
            try:
                idx = int(part) - 1
                if 0 <= idx < max_val:
                    indices.append(idx)
                else:
                    raise ValueError(f"Índice fuera de rango: {part}")
            except ValueError:
                raise ValueError(f"Índice inválido: {part}")

    # Remove duplicates and sort
    return sorted(set(indices))


def prompt_yes_no(prompt_text: str, default: bool = False) -> bool:
    """Prompt for yes/no confirmation."""
    return Confirm.ask(f"[prompt]{prompt_text}[/prompt]", default=default)


def prompt_int_range(
    prompt_text: str,
    min_val: int,
    max_val: int,
    default: Optional[int] = None,
) -> int:
    """Prompt for integer within range."""
    while True:
        default_str = str(default) if default is not None else ""
        val = Prompt.ask(
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
    new_val = Prompt.ask(
        f"[prompt]{key}[/prompt]{hint} [dim](actual: {current})[/dim]",
        default=current,
    ).strip()

    if value_type == "int":
        try:
            int(new_val)
        except ValueError:
            console.print("[error]Debe ser un número entero[/error]")
            return prompt_config_value(key, current, value_type)

    elif value_type == "bool":
        if new_val.lower() not in ("s", "n", "si", "no", "yes", "no", "true", "false"):
            console.print("[error]Debe ser s/n o true/false[/error]")
            return prompt_config_value(key, current, value_type)

    return new_val