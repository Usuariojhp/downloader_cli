"""Download commands for video, audio, and batch."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Optional, List

import typer
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    DownloadColumn,
    TransferSpeedColumn,
)

from media_dl.config import get_settings
from media_dl.core.extractors import get_extractor
from media_dl.core.strategies import StrategyFactory, build_strategy_args
from media_dl.core.history import HistoryRepository
from media_dl.core.progress import create_progress_hook
from media_dl.core.models import DownloadRequest
from media_dl.core.exceptions import MediaDLError, ExtractorError, DownloadError
from media_dl.ui import (
    show_header,
    create_media_info_table as show_media_info_table,
    show_success_panel,
    show_error_panel,
    show_warning_panel,
    prompt_yes_no,
    pause,
    get_console,
)
from media_dl.ui.tables import format_size

app = typer.Typer(name="download", help="Descargar video, audio o lote")


def _get_settings():
    return get_settings()


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _select_video_quality(info, settings) -> str:
    heights = info.available_heights
    if not heights:
        return "bestvideo+bestaudio/best"

    if settings.default_video_quality != "auto":
        try:
            target = int(settings.default_video_quality)
            if target in heights:
                return f"bestvideo[height<={target}]+bestaudio/best[height<={target}]/best"
        except ValueError:
            pass

    # For non-interactive, use best available
    if not settings.auto_subtitle:
        return "bestvideo+bestaudio/best"

    return "bestvideo+bestaudio/best"


def _build_ydl_opts(request: DownloadRequest, strategy_args: dict, settings) -> dict:
    output_template = os.path.join(
        request.output_path or settings.download_path,
        "%(title).100s [%(id)s].%(ext)s"
    )

    opts = {
        "outtmpl": output_template,
        "merge_output_format": "mp4",
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
        opts["format"] = request.quality or "bestvideo+bestaudio/best"
    else:
        if request.format == "mp3":
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(request.bitrate),
            }]
        else:
            opts["format"] = "bestaudio/best"

    if request.subtitles:
        opts["writesubtitles"] = True
        opts["writeautomaticsub"] = True
        opts["subtitleslangs"] = request.subtitles
        opts["subtitlesformat"] = "srt"

    if settings.embed_thumbnail:
        opts.setdefault("postprocessors", []).append({
            "key": "EmbedThumbnail",
            "already_have_thumbnail": False,
        })

    if settings.embed_metadata:
        opts.setdefault("postprocessors", []).append({
            "key": "FFmpegMetadata",
        })

    if settings.write_info_json:
        opts["writeinfojson"] = True

    return opts


def _download_with_retry(
    url: str,
    ydl_opts: dict,
    progress: Progress,
    task_id,
    max_attempts: int,
) -> str:
    from yt_dlp import YoutubeDL

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1:
                c = get_console()
                c.print(f"[warning]Reintentando... (intento {attempt}/{max_attempts})[/warning]")
                time.sleep(2)

            ydl_opts["progress_hooks"] = [create_progress_hook(progress, task_id)]

            with YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(result)

        except Exception as e:
            last_error = e
            if attempt == max_attempts:
                raise DownloadError(
                    f"Falló después de {max_attempts} intentos: {e}",
                    url=url,
                    cause=e,
                )

    raise last_error


@app.command("video")
def download_video(
    url: str = typer.Argument(..., help="URL del video"),
    quality: Optional[str] = typer.Option(None, "--quality", "-q", help="Calidad (auto, 1080, 720, etc.)"),
    ultra: bool = typer.Option(True, "--ultra/--normal", help="Modo ultra rápido (aria2c)"),
    subs: Optional[str] = typer.Option(None, "--subs", "-s", help="Subtítulos (ej: es,en)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Directorio de salida"),
    force: bool = typer.Option(False, "--force", "-f", help="Forzar descarga aunque exista"),
):
    """Descargar video"""
    settings = _get_settings()
    show_header("📹 DESCARGAR VIDEO", f"URL: {url}")

    try:
        console = get_console()
        console.print("[cyan]🔍 Analizando enlace...[/cyan]")
        extractor = get_extractor(url)
        info = _run_async(extractor.extract(url))

        console.print(show_media_info_table(info))

        repo = HistoryRepository()
        if settings.check_duplicates and not force:
            duplicate = repo.is_duplicate(url)
            if duplicate:
                show_warning_panel(
                    "⚠️ Duplicado Detectado",
                    f"Este video ya fue descargado:\n{duplicate.title}\n"
                    f"Fecha: {duplicate.download_date.strftime('%Y-%m-%d %H:%M')}\n"
                    f"Tamaño: {format_size(duplicate.file_size)}"
                )
                if not prompt_yes_no("¿Descargar de nuevo?", default=False):
                    console.print("[yellow]Descarga cancelada[/yellow]")
                    return

        format_str = quality or _select_video_quality(info, settings)

        strategy = StrategyFactory.get("aria2c" if ultra else "native")
        if not strategy.is_available() and ultra:
            show_warning_panel(
                "⚠️ Aria2c no disponible",
                "Se usará el modo normal. Instala aria2c para descargas ultra rápidas."
            )
            strategy = StrategyFactory.get("native")

        strategy_args = build_strategy_args(strategy, settings)

        request = DownloadRequest(
            url=url,
            media_type="video",
            quality=format_str,
            subtitles=subs.split(",") if subs else (settings.subtitle_languages if settings.auto_subtitle else []),
            strategy="ultra" if ultra else "normal",
            output_path=output,
            force=force,
        )

        ydl_opts = _build_ydl_opts(request, strategy_args, settings)

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40, style="cyan", complete_style="bright_cyan"),
            "[progress.percentage]{task.percentage:>3.0f}%",
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Descargando...", total=100)

            start_time = time.time()
            filepath = _download_with_retry(
                url, ydl_opts, progress, task, settings.retry_attempts
            )
            duration = time.time() - start_time

        file_path = Path(filepath)
        file_size = file_path.stat().st_size if file_path.exists() else 0

        repo.add(
            url=url,
            title=info.title,
            platform=info.platform,
            media_type="video",
            quality=format_str,
            file_path=str(file_path),
            file_size=file_size,
            duration=info.duration,
            uploader=info.uploader,
            thumbnail=info.thumbnail,
        )

        show_success_panel(
            "✅ Descarga Completada",
            f"Archivo: {file_path.name}\n"
            f"Tamaño: {format_size(file_size)}\n"
            f"Tiempo: {duration:.1f}s\n"
            f"Ubicación: {file_path}"
        )

    except MediaDLError as e:
        show_error_panel("❌ Error", str(e))
        raise typer.Exit(1)
    except Exception as e:
        show_error_panel("❌ Error Inesperado", f"{type(e).__name__}: {e}")
        raise typer.Exit(1)


@app.command("audio")
def download_audio(
    url: str = typer.Argument(..., help="URL del video/audio"),
    format: str = typer.Option("mp3", "--format", "-f", help="Formato: mp3 u original"),
    bitrate: int = typer.Option(192, "--bitrate", "-b", help="Bitrate MP3 (128, 192, 320)"),
    ultra: bool = typer.Option(True, "--ultra/--normal", help="Modo ultra rápido (aria2c)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Directorio de salida"),
    force: bool = typer.Option(False, "--force", "-f", help="Forzar descarga aunque exista"),
):
    """Descargar audio"""
    settings = _get_settings()
    show_header("🎵 DESCARGAR AUDIO", f"URL: {url}")

    try:
        console = get_console()
        console.print("[cyan]🔍 Analizando enlace...[/cyan]")
        extractor = get_extractor(url)
        info = _run_async(extractor.extract(url))

        console.print(show_media_info_table(info))

        repo = HistoryRepository()
        if settings.check_duplicates and not force:
            duplicate = repo.is_duplicate(url)
            if duplicate:
                show_warning_panel(
                    "⚠️ Duplicado Detectado",
                    f"Este audio ya fue descargado:\n{duplicate.title}"
                )
                if not prompt_yes_no("¿Descargar de nuevo?", default=False):
                    console.print("[yellow]Descarga cancelada[/yellow]")
                    return

        if format not in ("mp3", "original"):
            show_error_panel("Error", "Formato debe ser 'mp3' u 'original'")
            raise typer.Exit(1)

        if format == "mp3" and bitrate not in (128, 192, 320):
            show_error_panel("Error", "Bitrate debe ser 128, 192 o 320")
            raise typer.Exit(1)

        strategy = StrategyFactory.get("aria2c" if ultra else "native")
        if not strategy.is_available() and ultra:
            show_warning_panel("⚠️ Aria2c no disponible", "Usando modo normal")
            strategy = StrategyFactory.get("native")

        strategy_args = build_strategy_args(strategy, settings)

        request = DownloadRequest(
            url=url,
            media_type="audio",
            format=format,
            bitrate=bitrate,
            strategy="ultra" if ultra else "normal",
            output_path=output,
            force=force,
        )

        ydl_opts = _build_ydl_opts(request, strategy_args, settings)

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40, style="cyan", complete_style="bright_cyan"),
            "[progress.percentage]{task.percentage:>3.0f}%",
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Descargando audio...", total=100)

            start_time = time.time()
            filepath = _download_with_retry(
                url, ydl_opts, progress, task, settings.retry_attempts
            )
            duration = time.time() - start_time

        file_path = Path(filepath)
        if format == "mp3":
            file_path = file_path.with_suffix(".mp3")

        file_size = file_path.stat().st_size if file_path.exists() else 0

        repo.add(
            url=url,
            title=info.title,
            platform=info.platform,
            media_type="audio",
            quality=f"{format} {bitrate}kbps" if format == "mp3" else "original",
            file_path=str(file_path),
            file_size=file_size,
            duration=info.duration,
            uploader=info.uploader,
            thumbnail=info.thumbnail,
        )

        show_success_panel(
            "✅ Audio Descargado",
            f"Archivo: {file_path.name}\n"
            f"Formato: {format.upper()}" + (f" {bitrate}kbps" if format == "mp3" else "") + "\n"
            f"Tamaño: {format_size(file_size)}\n"
            f"Tiempo: {duration:.1f}s\n"
            f"Ubicación: {file_path}"
        )

    except MediaDLError as e:
        show_error_panel("❌ Error", str(e))
        raise typer.Exit(1)
    except Exception as e:
        show_error_panel("❌ Error Inesperado", f"{type(e).__name__}: {e}")
        raise typer.Exit(1)


@app.command("batch")
def download_batch(
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Archivo con URLs (una por línea)"),
    type: str = typer.Option("video", "--type", "-t", help="Tipo: video o audio"),
    concurrent: int = typer.Option(3, "--concurrent", "-c", help="Descargas concurrentes"),
    ultra: bool = typer.Option(True, "--ultra/--normal", help="Modo ultra rápido"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Directorio de salida"),
    format: str = typer.Option("mp3", "--format", help="Formato audio (si type=audio)"),
    bitrate: int = typer.Option(192, "--bitrate", help="Bitrate MP3"),
):
    """Descarga por lotes desde archivo o entrada"""
    settings = _get_settings()

    if file:
        urls = file.read_text().strip().splitlines()
    else:
        console = get_console()
        console.print("[dim]Pega URLs (una por línea, línea vacía para terminar):[/dim]")
        urls = []
        while True:
            url = typer.prompt("[prompt]URL[/prompt]", default="").strip()
            if not url:
                break
            urls.append(url)

    urls = [u.strip() for u in urls if u.strip() and (u.startswith("http://") or u.startswith("https://"))]

    if not urls:
        show_error_panel("Error", "No hay URLs válidas")
        raise typer.Exit(1)

    show_header("📋 DESCARGA POR LOTES", f"{len(urls)} URLs - Tipo: {type}")

    repo = HistoryRepository()
    strategy = StrategyFactory.get("aria2c" if ultra else "native")
    if not strategy.is_available() and ultra:
        strategy = StrategyFactory.get("native")

    strategy_args = build_strategy_args(strategy, settings)

    successful = 0
    failed = 0

    for idx, url in enumerate(urls, 1):
        console = get_console()
        console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
        console.print(f"[bold]📥 [{idx}/{len(urls)}] {url}[/bold]")
        console.print(f"[bold cyan]{'='*60}[/bold cyan]")

        try:
            extractor = get_extractor(url)
            info = _run_async(extractor.extract(url))

            if settings.check_duplicates:
                duplicate = repo.is_duplicate(url)
                if duplicate:
                    console.print(f"[yellow]⏭️ Saltando (ya descargado): {duplicate.title}[/yellow]")
                    continue

            if type == "video":
                format_str = _select_video_quality(info, settings)
                request = DownloadRequest(
                    url=url, media_type="video", quality=format_str,
                    strategy="ultra" if ultra else "normal", output_path=output
                )
            else:
                request = DownloadRequest(
                    url=url, media_type="audio", format=format, bitrate=bitrate,
                    strategy="ultra" if ultra else "normal", output_path=output
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
                task = progress.add_task(f"[cyan]{idx}/{len(urls)}", total=100)
                _download_with_retry(url, ydl_opts, progress, task, settings.retry_attempts)

            successful += 1

        except Exception as e:
            console.print(f"[error]❌ Error: {e}[/error]")
            failed += 1
            continue

    show_success_panel(
        "📊 Lote Completado",
        f"✅ Exitosas: {successful}\n"
        f"❌ Fallidas: {failed}\n"
        f"📁 Total: {len(urls)}"
    )