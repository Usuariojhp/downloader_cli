"""Playlist download command."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

import typer
from rich.markup import escape
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TransferSpeedColumn,
)

from media_dl.config import Settings, get_settings
from media_dl.core.cover import explain_embed_cover
from media_dl.core.exceptions import DownloadError, MediaDLError
from media_dl.core.extractors import get_extractor
from media_dl.core.history import HistoryRepository
from media_dl.core.models import DownloadRequest
from media_dl.core.progress import create_progress_hook
from media_dl.core.strategies import StrategyFactory, build_strategy_args
from media_dl.ui import (
    create_media_info_table as show_media_info_table,
)
from media_dl.ui import (
    get_console,
    parse_range,
    prompt_yes_no,
    show_error_panel,
    show_header,
    show_success_panel,
    show_warning_panel,
)
from media_dl.ui.tables import create_playlist_table

console = get_console()

BEST_VIDEO = "bestvideo+bestaudio/best"


def _get_settings() -> Settings:
    return get_settings()


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _merge_postprocessors(opts: dict[str, Any], settings: Settings) -> None:
    """Add thumbnail/metadata postprocessors once, keeping any provided ones."""
    postprocessors = list(opts.get("postprocessors") or [])
    present = {p.get("key") for p in postprocessors}

    if settings.embed_thumbnail and "EmbedThumbnail" not in present:
        postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    if settings.embed_metadata and "FFmpegMetadata" not in present:
        postprocessors.append({"key": "FFmpegMetadata"})

    if postprocessors:
        opts["postprocessors"] = postprocessors


def _build_ydl_opts(
    request: DownloadRequest, strategy_args: dict[str, Any], settings: Settings
) -> dict[str, Any]:
    """Build yt-dlp options from request and strategy."""
    base_path = Path(request.output_path or settings.download_path)
    output_template = str(base_path / "%(title).100s [%(id)s].%(ext)s")

    opts = {
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "noprogress": True,
        "retries": settings.retry_attempts,
        "fragment_retries": settings.retry_attempts,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-us,en;q=0.5",
            "Sec-Fetch-Mode": "navigate",
        },
        **strategy_args,
    }

    if request.media_type == "video":
        opts["format"] = request.quality or BEST_VIDEO
    elif request.format == "mp3":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(request.bitrate),
            }
        ]
    else:
        opts["format"] = "bestaudio/best"

    if request.subtitles:
        opts["writesubtitles"] = True
        opts["writeautomaticsub"] = True
        opts["subtitleslangs"] = request.subtitles
        opts["subtitlesformat"] = "srt"

    _merge_postprocessors(opts, settings)

    if settings.write_info_json:
        opts["writeinfojson"] = True

    return opts


def _download_single(
    url: str,
    ydl_opts: dict[str, Any],
    progress: Progress,
    task_id: TaskID,
    max_attempts: int,
) -> str:
    """Download single item with retry."""
    from yt_dlp import YoutubeDL

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1:
                time.sleep(2)

            ydl_opts["progress_hooks"] = [create_progress_hook(progress, task_id)]

            with YoutubeDL(ydl_opts) as ydl:  # type: ignore[no-untyped-call]
                result = ydl.extract_info(url, download=True)
                return cast(str, ydl.prepare_filename(result))

        except Exception as e:
            last_error = e
            if attempt == max_attempts:
                raise DownloadError(
                    f"Falló después de {max_attempts} intentos: {e}", url=url, cause=e
                ) from e

    raise DownloadError(
        f"No se intentó la descarga de {url} (intentos: {max_attempts})", url=url, cause=last_error
    ) from last_error


def playlist(
    ctx: typer.Context,
    url: str = typer.Argument(..., help="URL de la playlist"),
    range: str | None = typer.Option(
        None, "--range", "-r", help="Rango (ej: 1-5,10,15-20 o 'all')"
    ),
    media_type: str = typer.Option("video", "--type", "-t", help="Tipo: video o audio"),
    audio_format: str = typer.Option("mp3", "--format", "-f", help="Formato audio (si type=audio)"),
    bitrate: int = typer.Option(192, "--bitrate", "-b", help="Bitrate MP3 (128, 192, 320)"),
    ultra: bool = typer.Option(True, "--ultra/--normal", help="Modo ultra rápido"),
    output: str | None = typer.Option(None, "--output", "-o", help="Directorio de salida"),
) -> None:
    """Descargar playlist completa o rango"""
    settings = _get_settings()

    if media_type not in ("video", "audio"):
        show_error_panel("Error", "El tipo debe ser 'video' o 'audio'")
        raise typer.Exit(1)
    if audio_format not in ("mp3", "original"):
        show_error_panel("Error", "El formato debe ser 'mp3' u 'original'")
        raise typer.Exit(1)
    if audio_format == "mp3" and bitrate not in (128, 192, 320):
        show_error_panel("Error", "El bitrate debe ser 128, 192 o 320")
        raise typer.Exit(1)

    show_header("🎬 DESCARGAR PLAYLIST", f"URL: {url}")

    try:
        # Extract playlist info
        console.print("[cyan]🔍 Analizando playlist...[/cyan]")
        extractor = get_extractor(url)
        info = _run_async(extractor.extract(url))

        if not info.is_playlist:
            show_warning_panel(
                "⚠️ No es playlist",
                "La URL no parece ser una playlist. "
                "Usa 'media-dl download video' o 'media-dl download audio'.",
            )
            raise typer.Exit(1)

        # Show playlist info
        console.print(show_media_info_table(info))

        # Show entries
        console.print(create_playlist_table(info.entries, range))

        # Handle range
        selected_entries = info.entries
        if range:
            try:
                indices = parse_range(range, len(info.entries))
            except ValueError as e:
                show_error_panel("Error", str(e))
                raise typer.Exit(1) from e
            if indices is not None:
                selected_entries = [info.entries[i] for i in indices]

        console.print(
            f"\n[green]Se descargarán {len(selected_entries)} "
            f"de {len(info.entries)} elementos[/green]"
        )

        if not prompt_yes_no("¿Continuar?", default=True):
            console.print("[yellow]Cancelado[/yellow]")
            return

        # Get strategy
        strategy = StrategyFactory.get("aria2c" if ultra else "native")
        if not strategy.is_available() and ultra:
            show_warning_panel("⚠️ Aria2c no disponible", "Usando modo normal")
            strategy = StrategyFactory.get("native")

        strategy_args = build_strategy_args(strategy, settings)

        repo = HistoryRepository()
        successful = 0
        failed = 0

        for idx, entry in enumerate(selected_entries, 1):
            console.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
            console.print(f"[bold]📥 [{idx}/{len(selected_entries)}] {escape(entry.title)}[/bold]")
            console.print(f"[bold cyan]{'=' * 60}[/bold cyan]")

            try:
                # La URL de la entrada es la que va al historial; para bajar se
                # usa la directa si el extractor la resolvió.
                pagina_url = entry.url or f"https://www.youtube.com/watch?v={entry.id}"
                video_url = entry.media_url or pagina_url

                # Check duplicate
                if settings.check_duplicates:
                    duplicate = repo.is_duplicate(pagina_url)
                    if duplicate:
                        console.print(
                            f"[yellow]⏭️ Saltando (ya descargado): {duplicate.title}[/yellow]"
                        )
                        continue

                # Build request
                if media_type == "video":
                    request = DownloadRequest(
                        url=video_url,
                        media_type="video",
                        quality=BEST_VIDEO,
                        strategy="ultra" if ultra else "normal",
                        output_path=output,
                    )
                else:
                    request = DownloadRequest(
                        url=video_url,
                        media_type="audio",
                        format=cast('Literal["mp3", "original"]', audio_format),
                        bitrate=cast("Literal[128, 192, 320]", bitrate),
                        strategy="ultra" if ultra else "normal",
                        output_path=output,
                    )

                ydl_opts = _build_ydl_opts(request, strategy_args, settings)

                with Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(bar_width=30, style="cyan", complete_style="bright_cyan"),
                    "[progress.percentage]{task.percentage:>3.0f}%",
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(f"[cyan]{idx}/{len(selected_entries)}", total=100)
                    filepath = _download_single(
                        video_url, ydl_opts, progress, task, settings.retry_attempts
                    )

                # Save to history
                file_path = Path(filepath)
                if media_type == "audio" and audio_format == "mp3":
                    file_path = file_path.with_suffix(".mp3")

                file_size = file_path.stat().st_size if file_path.exists() else 0

                if settings.embed_thumbnail:
                    cover_ok, cover_reason = explain_embed_cover(file_path, entry.thumbnail)
                    if not cover_ok:
                        console.print(f"[yellow]⚠️  Portada no incrustada: {cover_reason}[/yellow]")

                repo.add(
                    url=pagina_url,
                    title=entry.title,
                    platform=info.platform,
                    media_type=media_type,
                    quality=(request.quality or BEST_VIDEO)
                    if media_type == "video"
                    else f"{audio_format} {bitrate}kbps",
                    file_path=str(file_path),
                    file_size=file_size,
                    duration=int(entry.duration) if entry.duration else None,
                    uploader=entry.uploader,
                    thumbnail=entry.thumbnail,
                )

                successful += 1

            except Exception as e:
                console.print(f"[error]❌ Error: {e}[/error]")
                failed += 1
                continue

        # Summary
        show_success_panel(
            "🎬 Playlist Completada",
            f"✅ Exitosas: {successful}\n"
            f"❌ Fallidas: {failed}\n"
            f"📊 Total procesados: {len(selected_entries)}",
        )

    except MediaDLError as e:
        show_error_panel("❌ Error", str(e))
        raise typer.Exit(1) from e
    except Exception as e:
        show_error_panel("❌ Error Inesperado", f"{type(e).__name__}: {e}")
        raise typer.Exit(1) from e


T = TypeVar("T")
