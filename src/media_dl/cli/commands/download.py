"""Download commands for video, audio, and batch."""

from __future__ import annotations

import asyncio
import glob
import time
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
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
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from media_dl.config import Settings, get_settings
from media_dl.core.cover import explain_embed_cover
from media_dl.core.exceptions import DownloadError, MediaDLError
from media_dl.core.extractors import get_extractor
from media_dl.core.history import HistoryRepository
from media_dl.core.models import DownloadRequest, MediaInfo
from media_dl.core.progress import create_progress_hook
from media_dl.core.strategies import StrategyFactory, build_strategy_args
from media_dl.ui import (
    create_media_info_table as show_media_info_table,
)
from media_dl.ui import (
    get_console,
    prompt_audio_bitrate,
    prompt_audio_format,
    prompt_quality,
    prompt_yes_no,
    show_error_panel,
    show_header,
    show_success_panel,
    show_warning_panel,
)
from media_dl.ui.console import is_interactive
from media_dl.ui.tables import format_size

app = typer.Typer(name="download", help="Descargar video, audio o lote")

console = get_console()


def _get_settings() -> Settings:
    return get_settings()


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


BEST_VIDEO = "bestvideo+bestaudio/best"


def _height_selector(height: int) -> str:
    return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"


def _select_video_quality(info: MediaInfo, settings: Settings, quality: str | None = None) -> str:
    """Build a yt-dlp format selector for the requested quality.

    ``quality`` accepts a height (480, 720, 1080p, ...) or 'auto'. When the
    requested height is not available the closest one below it is used, so the
    request is never silently upgraded.
    """
    target = quality if quality is not None else settings.default_video_quality
    normalized = str(target or "auto").strip().lower().rstrip("p")

    if normalized in ("", "auto"):
        return BEST_VIDEO

    try:
        wanted = int(normalized)
    except ValueError:
        return BEST_VIDEO

    heights = info.available_heights
    if not heights:
        return _height_selector(wanted)

    best = max((h for h in heights if h <= wanted), default=min(heights))
    return _height_selector(best)


def _fmt_date(value: datetime | None) -> str:
    """Format a download date, tolerating missing values."""
    return value.strftime("%Y-%m-%d %H:%M") if value else "N/A"


def _can_ask() -> bool:
    """Sólo preguntamos si hay una persona delante de la terminal.

    En scripts, tuberías o CI no hay a quién preguntar, así que se aplica la
    configuración sin molestar.
    """
    return is_interactive()


def _free_output_stem(directory: Path, stem: str) -> str:
    """Return a stem that no file in ``directory`` uses yet.

    El programa nunca pisa un archivo que ya existe: si vuelve a descargarse
    lo mismo, se crea una variante "titulo (1)", "(2)"... y el original se
    queda intacto.
    """
    if not any(directory.glob(f"{glob.escape(stem)}.*")):
        return stem

    counter = 1
    while any(directory.glob(f"{glob.escape(f'{stem} ({counter})')}.*")):
        counter += 1
    return f"{stem} ({counter})"


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
    request: DownloadRequest,
    strategy_args: dict[str, Any],
    settings: Settings,
    stem: str | None = None,
) -> dict[str, Any]:
    """Build yt-dlp options.

    ``stem`` fija el nombre sin extensión (la extensión la decide yt-dlp). Se
    usa para no sobrescribir: si el archivo ya existe, se le pasa una variante
    libre tipo "titulo (1)".
    """
    base_path = Path(request.output_path or settings.download_path)
    name = stem or "%(title).100s [%(id)s]"
    output_template = str(base_path / f"{name}.%(ext)s")

    opts = {
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "noprogress": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
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


def _download_with_retry(
    url: str,
    ydl_opts: dict[str, Any],
    progress: Progress,
    task_id: TaskID,
    max_attempts: int,
) -> str:
    from yt_dlp import YoutubeDL

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1:
                c = get_console()
                c.print(f"[warning]Reintentando... (intento {attempt}/{max_attempts})[/warning]")
                time.sleep(2)

            ydl_opts["progress_hooks"] = [create_progress_hook(progress, task_id)]

            with YoutubeDL(ydl_opts) as ydl:  # type: ignore[no-untyped-call]
                result = ydl.extract_info(url, download=True)
                return cast(str, ydl.prepare_filename(result))

        except Exception as e:
            last_error = e
            if attempt == max_attempts:
                raise DownloadError(
                    f"Falló después de {max_attempts} intentos: {e}",
                    url=url,
                    cause=e,
                ) from e

    raise DownloadError(
        f"No se intentó la descarga de {url} (intentos: {max_attempts})", url=url, cause=last_error
    ) from last_error


def _output_stem_for(
    info: Any,
    settings: Settings,
    request: DownloadRequest,
    *,
    duplicate: Any = None,
) -> str | None:
    """Nombre de salida cuando hay que conservar lo ya descargado.

    Devuelve None si no hay conflicto: entonces manda la plantilla normal.
    """
    if duplicate is None:
        return None

    directory = Path(request.output_path or settings.download_path)
    directory.mkdir(parents=True, exist_ok=True)
    titulo = info.title[:80].strip() or info.id
    return _free_output_stem(directory, f"{titulo} [{info.id}]")


def run_video(
    url: str,
    quality: str | None = None,
    ultra: bool = True,
    subs: str | None = None,
    output: str | None = None,
    force: bool = False,
) -> None:
    """Download a single video. Plain function, safe to call from other code."""
    settings = _get_settings()
    show_header("📹 DESCARGAR VIDEO", f"URL: {url}")

    try:
        console.print("[cyan]🔍 Analizando enlace...[/cyan]")
        extractor = get_extractor(url)
        info = _run_async(extractor.extract(url))

        console.print(show_media_info_table(info))

        repo = HistoryRepository()
        duplicate = None
        if settings.check_duplicates and not force:
            duplicate = repo.is_duplicate(url)
            if duplicate:
                show_warning_panel(
                    "⚠️ Duplicado Detectado",
                    f"Este video ya fue descargado:\n{duplicate.title}\n"
                    f"Fecha: {_fmt_date(duplicate.download_date)}\n"
                    f"Tamaño: {format_size(duplicate.file_size)}",
                )
                if not prompt_yes_no("¿Descargar de nuevo?", default=False):
                    console.print("[yellow]Descarga cancelada[/yellow]")
                    return
                console.print(
                    "[cyan]Se conservará el archivo anterior; "
                    "el nuevo se guardará con otro nombre[/cyan]"
                )

        if quality is None and _can_ask() and info.available_heights:
            quality = prompt_quality(
                [str(h) for h in info.available_heights],
                default=str(settings.default_video_quality),
            )

        format_str = _select_video_quality(info, settings, quality)

        strategy = StrategyFactory.get("aria2c" if ultra else "native")
        if not strategy.is_available() and ultra:
            show_warning_panel(
                "⚠️ Aria2c no disponible",
                "Se usará el modo normal. Instala aria2c para descargas ultra rápidas.",
            )
            strategy = StrategyFactory.get("native")

        strategy_args = build_strategy_args(strategy, settings)

        # Si el extractor resolvió una URL directa de audio (Spotify, etc.),
        # se descarga esa; si no, la de la página.
        destino = info.media_url or url

        request = DownloadRequest(
            url=destino,
            media_type="video",
            quality=format_str,
            subtitles=subs.split(",")
            if subs
            else (settings.subtitle_languages if settings.auto_subtitle else []),
            strategy="ultra" if ultra else "normal",
            output_path=output,
            force=force,
        )

        stem = _output_stem_for(info, settings, request, duplicate=duplicate)
        ydl_opts = _build_ydl_opts(request, strategy_args, settings, stem=stem)

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
                destino, ydl_opts, progress, task, settings.retry_attempts
            )
            duration = time.time() - start_time

        file_path = Path(filepath)
        if not file_path.exists():
            show_warning_panel(
                "⚠️ No se creó el archivo",
                f"Se esperaba aquí:\n{file_path}\n\n"
                "Puede que el archivo ya existiera con ese nombre. "
                "Prueba con -F para forzar la descarga.",
            )
            return

        file_size = file_path.stat().st_size

        repo.add(
            url=url,
            title=info.title,
            platform=info.platform,
            media_type="video",
            quality=format_str,
            file_path=str(file_path),
            file_size=file_size,
            duration=int(info.duration) if info.duration else None,
            uploader=info.uploader,
            thumbnail=info.thumbnail,
        )

        show_success_panel(
            "✅ Descarga Completada",
            f"Archivo: {file_path.name}\n"
            f"Tamaño: {format_size(file_size)}\n"
            f"Tiempo: {duration:.1f}s\n"
            f"Ubicación: {file_path}",
        )

    except MediaDLError as e:
        show_error_panel("❌ Error", str(e))
        raise typer.Exit(1) from e
    except Exception as e:
        show_error_panel("❌ Error Inesperado", f"{type(e).__name__}: {e}")
        raise typer.Exit(1) from e


def run_audio(
    url: str,
    audio_format: str | None = None,
    bitrate: int | None = None,
    ultra: bool = True,
    output: str | None = None,
    force: bool = False,
) -> None:
    """Download audio from a URL. Plain function, safe to call from other code."""
    settings = _get_settings()
    show_header("🎵 DESCARGAR AUDIO", f"URL: {url}")

    try:
        console.print("[cyan]🔍 Analizando enlace...[/cyan]")
        extractor = get_extractor(url)
        info = _run_async(extractor.extract(url))

        console.print(show_media_info_table(info))

        repo = HistoryRepository()
        duplicate = None
        if settings.check_duplicates and not force:
            duplicate = repo.is_duplicate(url)
            if duplicate:
                show_warning_panel(
                    "⚠️ Duplicado Detectado", f"Este audio ya fue descargado:\n{duplicate.title}"
                )
                if not prompt_yes_no("¿Descargar de nuevo?", default=False):
                    console.print("[yellow]Descarga cancelada[/yellow]")
                    return

        if _can_ask():
            if audio_format is None:
                audio_format = prompt_audio_format(default=settings.default_audio_format)
            if audio_format == "mp3" and bitrate is None:
                bitrate = prompt_audio_bitrate(default=settings.default_audio_bitrate)

        audio_format = audio_format or settings.default_audio_format
        bitrate = bitrate or settings.default_audio_bitrate

        if audio_format not in ("mp3", "original"):
            show_error_panel("Error", "Formato debe ser 'mp3' u 'original'")
            raise typer.Exit(1)

        if audio_format == "mp3" and bitrate not in (128, 192, 320):
            show_error_panel("Error", "Bitrate debe ser 128, 192 o 320")
            raise typer.Exit(1)

        strategy = StrategyFactory.get("aria2c" if ultra else "native")
        if not strategy.is_available() and ultra:
            show_warning_panel("⚠️ Aria2c no disponible", "Usando modo normal")
            strategy = StrategyFactory.get("native")

        strategy_args = build_strategy_args(strategy, settings)

        destino = info.media_url or url

        request = DownloadRequest(
            url=destino,
            media_type="audio",
            format=cast('Literal["mp3", "original"]', audio_format),
            bitrate=cast("Literal[128, 192, 320]", bitrate),
            strategy="ultra" if ultra else "normal",
            output_path=output,
            force=force,
        )

        stem = _output_stem_for(info, settings, request, duplicate=duplicate)
        ydl_opts = _build_ydl_opts(request, strategy_args, settings, stem=stem)

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
                destino, ydl_opts, progress, task, settings.retry_attempts
            )
            duration = time.time() - start_time

        file_path = Path(filepath)
        if audio_format == "mp3":
            file_path = file_path.with_suffix(".mp3")

        if not file_path.exists():
            show_warning_panel(
                "⚠️ No se creó el archivo",
                f"Se esperaba aquí:\n{file_path}\n\n"
                "Puede que el archivo ya existiera con ese nombre. "
                "Prueba con -F para forzar la descarga.",
            )
            return

        file_size = file_path.stat().st_size

        cover_note = ""
        if settings.embed_thumbnail:
            cover_ok, cover_reason = explain_embed_cover(file_path, info.thumbnail)
            if not cover_ok:
                # Se avisa en vez de callar: una descarga sin portada parece
                # un fallo del extractor cuando en realidad puede ser que la
                # imagen no se bajara, y sin el motivo no hay manera de saberlo.
                cover_note = f"\n⚠️  Portada no incrustada: {cover_reason}"

        repo.add(
            url=url,
            title=info.title,
            platform=info.platform,
            media_type="audio",
            quality=f"{audio_format} {bitrate}kbps" if audio_format == "mp3" else "original",
            file_path=str(file_path),
            file_size=file_size,
            duration=int(info.duration) if info.duration else None,
            uploader=info.uploader,
            thumbnail=info.thumbnail,
        )

        show_success_panel(
            "✅ Audio Descargado",
            f"Archivo: {file_path.name}\n"
            f"Formato: {audio_format.upper()}"
            + (f" {bitrate}kbps" if audio_format == "mp3" else "")
            + "\n"
            f"Tamaño: {format_size(file_size)}\n"
            f"Tiempo: {duration:.1f}s\n"
            f"Ubicación: {file_path}" + cover_note,
        )

    except MediaDLError as e:
        show_error_panel("❌ Error", str(e))
        raise typer.Exit(1) from e
    except Exception as e:
        show_error_panel("❌ Error Inesperado", f"{type(e).__name__}: {e}")
        raise typer.Exit(1) from e


def _build_batch_request(
    url: str,
    info: MediaInfo,
    media_type: str,
    settings: Settings,
    output: str | None,
    ultra: bool,
    audio_format: str,
    bitrate: int,
) -> DownloadRequest:
    """Build the download request for one batch entry."""
    strategy: Literal["ultra", "normal"] = "ultra" if ultra else "normal"

    if media_type == "video":
        return DownloadRequest(
            url=url,
            media_type="video",
            quality=_select_video_quality(info, settings),
            strategy=strategy,
            output_path=output,
        )

    return DownloadRequest(
        url=url,
        media_type="audio",
        format=cast('Literal["mp3", "original"]', audio_format),
        bitrate=cast("Literal[128, 192, 320]", bitrate),
        strategy=strategy,
        output_path=output,
    )


def _download_batch_item(
    url: str,
    request: DownloadRequest,
    strategy_args: dict[str, Any],
    settings: Settings,
    progress: Progress,
    task_id: TaskID,
) -> str:
    """Download one batch entry and return the resulting file path."""
    ydl_opts = _build_ydl_opts(request, strategy_args, settings)
    return _download_with_retry(url, ydl_opts, progress, task_id, settings.retry_attempts)


def run_batch(
    file: Path | None = None,
    media_type: str = "video",
    concurrent: int = 3,
    ultra: bool = True,
    output: str | None = None,
    audio_format: str = "mp3",
    bitrate: int = 192,
    urls: list[str] | None = None,
) -> None:
    """Download a list of URLs. Plain function, safe to call from other code."""
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

    workers = max(1, min(concurrent, 8))

    if urls is None and file is not None:
        if not file.is_file():
            show_error_panel("Error", f"No existe el archivo: {file}")
            raise typer.Exit(1)
        urls = file.read_text().strip().splitlines()
    elif urls is None:
        console.print("[dim]Pega URLs (una por línea, línea vacía para terminar):[/dim]")
        collected: list[str] = []
        while True:
            url = typer.prompt("[prompt]URL[/prompt]", default="").strip()
            if not url:
                break
            collected.append(url)
        urls = collected

    urls = [u.strip() for u in urls if u.strip() and u.startswith(("http://", "https://"))]

    if not urls:
        show_error_panel("Error", "No hay URLs válidas")
        raise typer.Exit(1)

    show_header(
        "📋 DESCARGA POR LOTES",
        f"{len(urls)} URLs - Tipo: {media_type} - {workers} en paralelo",
    )

    repo = HistoryRepository()
    strategy = StrategyFactory.get("aria2c" if ultra else "native")
    if not strategy.is_available() and ultra:
        show_warning_panel("⚠️ Aria2c no disponible", "Se usará el modo normal")
        strategy = StrategyFactory.get("native")

    strategy_args = build_strategy_args(strategy, settings)

    # Fase 1: resolver metadatos y descartar duplicados (secuencial, para no
    # saturar la red antes de descargar).
    jobs: list[tuple[str, DownloadRequest, MediaInfo]] = []
    skipped = 0
    failed = 0

    for url in urls:
        try:
            info = _run_async(get_extractor(url).extract(url))
        except Exception as e:
            console.print(f"[error]❌ {escape(url)}: {type(e).__name__}: {escape(str(e))}[/error]")
            failed += 1
            continue

        if settings.check_duplicates and (duplicate := repo.is_duplicate(url)):
            console.print(f"[yellow]⏭️ Saltando (ya descargado): {escape(duplicate.title)}[/yellow]")
            skipped += 1
            continue

        request = _build_batch_request(
            url, info, media_type, settings, output, ultra, audio_format, bitrate
        )
        jobs.append((url, request, info))

    if not jobs:
        show_warning_panel(
            "📊 Lote Finalizado",
            f"Sin descargas nuevas.\n⏭️ Saltados: {skipped}\n❌ Fallidos: {failed}",
        )
        return

    # Fase 2: descarga en paralelo con una barra de progreso compartida.
    results: dict[str, tuple[DownloadRequest, str, str | None]] = {}

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=24, style="cyan", complete_style="bright_cyan"),
        "[progress.percentage]{task.percentage:>3.0f}%",
        DownloadColumn(),
        TransferSpeedColumn(),
        console=console,
    ) as progress:
        task_ids = {
            url: progress.add_task(f"[cyan]{idx}/{len(jobs)} {url[:44]}[/cyan]", total=100)
            for idx, (url, _, _) in enumerate(jobs, 1)
        }

        def _run(url: str, request: DownloadRequest) -> None:
            filepath = _download_batch_item(
                url, request, strategy_args, settings, progress, task_ids[url]
            )
            results[url] = (request, filepath, None)

        def _record_failure(url: str, request: DownloadRequest, exc: BaseException) -> None:
            results[url] = (request, "", f"{type(exc).__name__}: {exc}")

        if workers > 1 and len(jobs) > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(_run, url, request): (url, request) for url, request, _ in jobs
                }
                for future in as_completed(futures):
                    url, request = futures[future]
                    try:
                        future.result()
                    except Exception as exc:
                        _record_failure(url, request, exc)
        else:
            for url, request, _ in jobs:
                try:
                    _run(url, request)
                except Exception as exc:
                    _record_failure(url, request, exc)

    # Fase 3: historial en el hilo principal (SQLite sin concurrencia).
    successful = 0
    for url, request, info in jobs:
        request_outcome, filepath, error = results.get(url, (request, "", "sin resultado"))

        if error is not None or not filepath or not Path(filepath).exists():
            failed += 1
            detalle = escape(str(error or filepath or "sin resultado"))
            console.print(f"[error]❌ {escape(url)}: {detalle}[/error]")
            continue

        path = Path(filepath)
        if media_type == "audio" and audio_format == "mp3":
            path = path.with_suffix(".mp3")
        size = path.stat().st_size if path.exists() else 0

        repo.add(
            url=url,
            title=info.title,
            platform=info.platform,
            media_type=media_type,
            quality=request_outcome.quality
            or (f"{audio_format} {bitrate}kbps" if audio_format == "mp3" else "original"),
            file_path=str(path),
            file_size=size,
            duration=int(info.duration) if info.duration else None,
            uploader=info.uploader,
            thumbnail=info.thumbnail,
        )
        successful += 1

    show_success_panel(
        "📊 Lote Completado",
        f"✅ Exitosas: {successful}\n"
        f"❌ Fallidas: {failed}\n"
        f"⏭️ Saltadas: {skipped}\n"
        f"📁 Total: {len(urls)}",
    )


@app.command("video")
def download_video(
    url: str = typer.Argument(..., help="URL del video"),
    quality: str | None = typer.Option(
        None, "--quality", "-q", help="Calidad (auto, 1080, 720...); pregunta si se omite"
    ),
    ultra: bool = typer.Option(True, "--ultra/--normal", help="Modo ultra rápido (aria2c)"),
    subs: str | None = typer.Option(None, "--subs", "-s", help="Subtítulos (ej: es,en)"),
    output: str | None = typer.Option(None, "--output", "-o", help="Directorio de salida"),
    force: bool = typer.Option(False, "--force", "-F", help="Forzar descarga aunque exista"),
) -> None:
    """Descargar video"""
    run_video(url=url, quality=quality, ultra=ultra, subs=subs, output=output, force=force)


@app.command("audio")
def download_audio(
    url: str = typer.Argument(..., help="URL del video/audio"),
    audio_format: str | None = typer.Option(
        None, "--format", "-f", help="Formato: mp3 u original (pregunta si se omite)"
    ),
    bitrate: int | None = typer.Option(
        None, "--bitrate", "-b", help="Bitrate MP3: 128, 192, 320 (pregunta si se omite)"
    ),
    ultra: bool = typer.Option(True, "--ultra/--normal", help="Modo ultra rápido (aria2c)"),
    output: str | None = typer.Option(None, "--output", "-o", help="Directorio de salida"),
    force: bool = typer.Option(False, "--force", "-F", help="Forzar descarga aunque exista"),
) -> None:
    """Descargar audio"""
    run_audio(
        url=url,
        audio_format=audio_format,
        bitrate=bitrate,
        ultra=ultra,
        output=output,
        force=force,
    )


@app.command("batch")
def download_batch(
    file: Path | None = typer.Option(None, "--file", "-f", help="Archivo con URLs (una por línea)"),
    media_type: str = typer.Option("video", "--type", "-t", help="Tipo: video o audio"),
    concurrent: int = typer.Option(3, "--concurrent", "-c", help="Descargas concurrentes (1-8)"),
    ultra: bool = typer.Option(True, "--ultra/--normal", help="Modo ultra rápido"),
    output: str | None = typer.Option(None, "--output", "-o", help="Directorio de salida"),
    audio_format: str = typer.Option("mp3", "--format", help="Formato audio (si type=audio)"),
    bitrate: int = typer.Option(192, "--bitrate", help="Bitrate MP3"),
) -> None:
    """Descarga por lotes desde archivo o entrada"""
    run_batch(
        file=file,
        media_type=media_type,
        concurrent=concurrent,
        ultra=ultra,
        output=output,
        audio_format=audio_format,
        bitrate=bitrate,
    )


T = TypeVar("T")
