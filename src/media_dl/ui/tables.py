"""Formatted tables for displaying information."""

from __future__ import annotations

from typing import Any

from rich.table import Table
from rich.text import Text

from media_dl.core.history.models import DownloadHistory
from media_dl.core.models import Format, MediaInfo, PlaylistEntry
from media_dl.ui.console import get_console
from media_dl.ui.theme import (
    TABLE_BOX,
    TABLE_HEADER_STYLE,
)

console = get_console()


def format_size(size: int | None) -> str:
    """Format file size in human readable format."""
    if size is None or size == 0:
        return "Desconocido"

    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} PB"


def format_duration(seconds: float | None) -> str:
    """Format duration as human readable string."""
    if not seconds:
        return "N/A"
    hours, rem = divmod(int(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"


def _cell(value: object, style: str = "") -> Text:
    """Wrap a value so Rich never interprets it as console markup.

    Los títulos y nombres de archivo contienen corchetes con frecuencia
    (nuestro template es '%(title).100s [%(id)s].%(ext)s'), y sin esto Rich se
    come el '[id]' como si fuera una etiqueta de estilo.
    """
    return Text(str(value), style=style) if style else Text(str(value))


def create_media_info_table(info: MediaInfo) -> Table:
    """Create table with media information."""
    table = Table(
        show_header=False,
        box=TABLE_BOX,
        border_style="cyan",
        padding=(0, 1),
    )
    table.add_column("Campo", style="bold yellow", width=20)
    table.add_column("Valor", style="white")

    table.add_row("📺 Título", _cell(info.title))
    table.add_row("👤 Canal", _cell(info.uploader or "N/A"))
    table.add_row("⏱️ Duración", format_duration(info.duration))
    table.add_row("🌐 Plataforma", _cell(info.platform))
    table.add_row("🔗 URL", _cell(info.url[:60] + "..." if len(info.url) > 60 else info.url))

    if info.estimated_size:
        table.add_row("💾 Tamaño est.", format_size(info.estimated_size))

    if info.view_count:
        table.add_row("👁️ Vistas", f"{info.view_count:,}")

    if info.is_playlist:
        table.add_row("📋 Tipo", "Playlist")
        table.add_row("📊 Elementos", str(len(info.entries)))
    else:
        table.add_row("📋 Tipo", "Video individual")

    return table


def create_format_table(formats: list[Format], media_type: str = "video") -> Table:
    """Create table with available formats."""
    table = Table(
        show_header=True,
        header_style=TABLE_HEADER_STYLE,
        box=TABLE_BOX,
        border_style="cyan",
    )

    if media_type == "video":
        table.add_column("#", style="dim", width=4, justify="center")
        table.add_column("Resolución", style="cyan", width=12)
        table.add_column("Ext", style="green", width=6)
        table.add_column("Codec Video", style="white", width=12)
        table.add_column("Codec Audio", style="white", width=12)
        table.add_column("Tamaño", style="yellow", width=10)
        table.add_column("Bitrate", style="magenta", width=10)
        table.add_column("Nota", style="dim cyan")

        video_formats = [f for f in formats if f.is_video]
        for idx, f in enumerate(video_formats, 1):
            size = (
                format_size(f.filesize or f.filesize_approx)
                if f.filesize or f.filesize_approx
                else "N/A"
            )
            table.add_row(
                str(idx),
                _cell(f.resolution or f"{f.height}p" if f.height else "N/A"),
                _cell(f.ext),
                _cell(f.vcodec or "N/A"),
                _cell(f.acodec or "N/A"),
                size,
                f"{f.tbr:.0f}k" if f.tbr else "N/A",
                _cell(f.quality_note or ""),
            )
    else:
        table.add_column("#", style="dim", width=4, justify="center")
        table.add_column("Ext", style="green", width=6)
        table.add_column("Codec", style="white", width=12)
        table.add_column("Bitrate", style="magenta", width=10)
        table.add_column("Tamaño", style="yellow", width=10)

        audio_formats = [f for f in formats if f.is_audio and not f.is_video]
        for idx, f in enumerate(audio_formats, 1):
            size = (
                format_size(f.filesize or f.filesize_approx)
                if f.filesize or f.filesize_approx
                else "N/A"
            )
            table.add_row(
                str(idx),
                _cell(f.ext),
                _cell(f.acodec or "N/A"),
                f"{f.abr:.0f}k" if f.abr else "N/A",
                size,
            )

    return table


def create_history_table(history: list[DownloadHistory], limit: int = 20) -> Table:
    """Create table with download history."""
    table = Table(
        show_header=True,
        header_style=TABLE_HEADER_STYLE,
        box=TABLE_BOX,
        border_style="cyan",
    )
    table.add_column("#", style="dim", width=4, justify="center")
    table.add_column("Título", style="cyan", max_width=40)
    table.add_column("Plataforma", style="yellow", width=12)
    table.add_column("Tipo", style="green", width=8)
    table.add_column("Tamaño", style="blue", width=10)
    table.add_column("Fecha", style="dim", width=18)

    for idx, record in enumerate(history, 1):
        title = record.title[:37] + "..." if len(record.title) > 40 else record.title
        table.add_row(
            str(idx),
            _cell(title),
            _cell(record.platform),
            _cell(record.media_type),
            format_size(record.file_size),
            record.download_date.strftime("%Y-%m-%d %H:%M") if record.download_date else "N/A",
        )

    return table


def create_config_table(config: dict[str, Any]) -> Table:
    """Create table with configuration settings."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=TABLE_BOX,
        border_style="cyan",
        padding=(0, 1),
    )
    table.add_column("Configuración", style="white", width=35)
    table.add_column("Valor Actual", style="green")

    items = [
        ("Carpeta de descargas", config.get("download_path", "./downloads")),
        ("Modo de descarga", config.get("download_mode", "ultra")),
        ("Calidad video por defecto", config.get("default_video_quality", "auto")),
        ("Formato audio por defecto", config.get("default_audio_format", "mp3")),
        ("Calidad audio por defecto", f"{config.get('default_audio_bitrate', 192)} kbps"),
        ("Subtítulos automáticos", str(config.get("auto_subtitle", False))),
        ("Idiomas subtítulos", ", ".join(config.get("subtitle_languages", ["es", "en"]))),
        ("Intentos de reintento", str(config.get("retry_attempts", 3))),
        ("Verificar duplicados", str(config.get("check_duplicates", True))),
        ("Conexiones Aria2c", str(config.get("aria2c_connections", 16))),
        ("Límite velocidad (KB/s)", str(config.get("max_download_speed", 0)) + " (0=sin límite)"),
        ("Descargas concurrentes", str(config.get("concurrent_downloads", 3))),
        ("Incrustar miniatura", str(config.get("embed_thumbnail", True))),
        ("Incrustar metadatos", str(config.get("embed_metadata", True))),
        ("Escribir info.json", str(config.get("write_info_json", False))),
    ]

    for name, value in items:
        table.add_row(name, str(value))

    return table


def create_system_info_table(
    python_version: str,
    ytdlp_version: str,
    aria2c_available: bool,
    ffmpeg_available: bool,
    spotdl_available: bool,
    scdl_available: bool,
    download_path: str,
    db_path: str,
) -> Table:
    """Create system information table."""
    table = Table(
        show_header=False,
        box=TABLE_BOX,
        border_style="cyan",
        padding=(0, 1),
    )
    table.add_column("Componente", style="yellow", width=25)
    table.add_column("Estado", style="white")

    table.add_row("Python", f"✅ {python_version}")
    table.add_row("yt-dlp", f"✅ {ytdlp_version}")
    table.add_row("aria2c", "✅ Disponible" if aria2c_available else "❌ No instalado")
    table.add_row("ffmpeg", "✅ Disponible" if ffmpeg_available else "❌ No instalado")
    table.add_row("spotdl", "✅ Disponible" if spotdl_available else "❌ No instalado (opcional)")
    table.add_row("scdl", "✅ Disponible" if scdl_available else "❌ No instalado (opcional)")
    table.add_row("", "")
    table.add_row("Carpeta descargas", _cell(f"📁 {download_path}"))
    table.add_row("Base de datos", _cell(f"📄 {db_path}"))

    return table


def create_stats_table(stats: dict[str, Any]) -> Table:
    """Create statistics table."""
    table = Table(
        show_header=True,
        header_style=TABLE_HEADER_STYLE,
        box=TABLE_BOX,
        border_style="cyan",
    )
    table.add_column("Métrica", style="cyan")
    table.add_column("Valor", style="white")

    table.add_row("Total descargas", str(stats.get("total_downloads", 0)))
    table.add_row("Tamaño total", format_size(stats.get("total_size_bytes", 0)))

    by_platform = stats.get("by_platform", {})
    if by_platform:
        table.add_row("", "")
        table.add_row("[bold]Por plataforma[/bold]", "")
        for platform, count in sorted(by_platform.items(), key=lambda x: -x[1]):
            table.add_row(_cell(f"  {platform}"), str(count))

    by_type = stats.get("by_type", {})
    if by_type:
        table.add_row("", "")
        table.add_row("[bold]Por tipo[/bold]", "")
        for mtype, count in sorted(by_type.items(), key=lambda x: -x[1]):
            table.add_row(_cell(f"  {mtype}"), str(count))

    return table


def create_playlist_table(entries: list[PlaylistEntry], selected_range: str | None = None) -> Table:
    """Create playlist entries table."""
    table = Table(
        show_header=True,
        header_style=TABLE_HEADER_STYLE,
        box=TABLE_BOX,
        border_style="cyan",
    )
    table.add_column("#", style="dim", width=4, justify="center")
    table.add_column("Título", style="cyan", max_width=50)
    table.add_column("Duración", style="yellow", width=10)
    table.add_column("Canal", style="green", width=20)

    for idx, entry in enumerate(entries, 1):
        is_selected = True
        if selected_range:
            # Simple range parsing - could be improved
            is_selected = str(idx) in selected_range.replace(" ", "").split(",")

        style = "bold white" if is_selected else "white"
        title = entry.title[:47] + "..." if len(entry.title) > 50 else entry.title

        table.add_row(
            str(idx),
            _cell(title, style=style),
            format_duration(entry.duration),
            _cell(
                (entry.uploader[:17] + "...")
                if entry.uploader and len(entry.uploader) > 20
                else (entry.uploader or ""),
                style=style,
            ),
            style=style,
        )

    return table
