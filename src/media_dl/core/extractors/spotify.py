"""Spotify extractor using spotdl (lazy loaded)."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from media_dl.core.exceptions import ExtractorError
from media_dl.core.extractors.base import Extractor, register_extractor
from media_dl.core.models import Format, MediaInfo, PlaylistEntry
from media_dl.ui.console import get_console

_spotdl_available: bool | None = None

#: Proveedores de audio de spotdl, en el orden en que los prueba él mismo.
#: Se usan para obtener una URL de audio real, porque la API de Spotify no
#: entrega ficheros sino solo metadatos.
AUDIO_PROVIDERS = ("YouTubeMusic", "Piped", "SoundCloud", "BandCamp")


def check_spotdl() -> bool:
    """Check if spotdl is available."""
    global _spotdl_available
    if _spotdl_available is None:
        try:
            import spotdl  # noqa: F401

            _spotdl_available = True
        except ImportError:
            _spotdl_available = False
    return _spotdl_available


def _audio_format() -> Format:
    """Descriptor del formato que spotdl entrega (MP3 de alta calidad)."""
    return Format(
        format_id="spotify_best",
        ext="mp3",
        vcodec="none",
        acodec="mp3",
        abr=320,
        quality_note="320kbps MP3",
    )


@register_extractor
class SpotifyExtractor(Extractor):
    """Spotify extractor using spotdl."""

    name = "spotify"
    domains: ClassVar[list[str]] = ["open.spotify.com", "spotify.com"]
    priority = 90

    def __init__(self) -> None:
        super().__init__()
        self._spotdl: Any = None
        self._downloader: Any = None

    def _ensure_spotdl(self) -> Any:
        """Lazy import and initialize spotdl."""
        if not check_spotdl():
            raise ExtractorError(
                "spotdl not installed. Install with: pip install 'media-dl[spotify]'",
                platform="Spotify",
            )
        if self._spotdl is None:
            from spotdl import Spotdl

            from media_dl.config import get_settings

            settings = get_settings()

            # Initialize with credentials if provided (for higher rate limits)
            self._spotdl = Spotdl(
                client_id=settings.spotify_client_id or "",
                client_secret=settings.spotify_client_secret or "",
                user_auth=False,
                no_cache=True,
                headless=True,
            )

    def _resolve_media_url(self, song: Any) -> str | None:
        """Find a real audio URL for a track using spotdl's audio providers.

        La API de Spotify no da ficheros, así que spotdl busca la misma canción
        en fuentes de audio gratuitás. Devolvemos la URL para que la descarga la
        haga yt-dlp, que sí sabe bajarla.
        """
        import spotdl.providers.audio as providers

        for name in AUDIO_PROVIDERS:
            provider_cls = getattr(providers, name, None)
            if provider_cls is None:
                continue
            try:
                url = provider_cls().search(song)
            except Exception:  # un proveedor que falle no debe parar el resto
                continue
            if url:
                return str(url)
        return None

    def can_handle(self, url: str) -> bool:
        return super().can_handle(url) and check_spotdl()

    async def extract(self, url: str) -> MediaInfo:
        """Extract Spotify track/playlist/album info."""
        self.validate_url(url)

        if not check_spotdl():
            raise ExtractorError(
                "spotdl not available. Install with: pip install 'media-dl[spotify]'",
                url=url,
                platform="Spotify",
            )

        self._ensure_spotdl()

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, self._extract_sync, url)

        return info

    def _extract_sync(self, url: str) -> MediaInfo:
        """Synchronous extraction using spotdl."""
        from spotdl.types.album import Album
        from spotdl.types.playlist import Playlist

        try:
            # Search for the content
            results = self._spotdl.search([url])

            if not results:
                raise ExtractorError("No results found", url=url, platform="Spotify")

            # Handle different types
            first = results[0]

            if isinstance(first, Playlist):
                return self._parse_playlist(first, url)
            elif isinstance(first, Album):
                return self._parse_album(first, url)
            else:
                return self._parse_track(first, url)

        except Exception as e:
            raise ExtractorError(
                f"Spotify extraction failed: {e}", url=url, platform="Spotify", cause=e
            ) from e

    def _parse_track(self, song: Any, url: str) -> MediaInfo:
        """Parse single track."""
        media_url = self._resolve_media_url(song)
        if not media_url:
            raise ExtractorError(
                f"No se ha encontrado audio para {song.name!r} en ninguna fuente "
                "(YouTube Music, Piped, SoundCloud, BandCamp)",
                url=url,
                platform="Spotify",
            )

        format_obj = _audio_format()

        return MediaInfo(
            id=song.song_id or "",
            title=song.name,
            url=url,
            platform="Spotify",
            uploader=", ".join(song.artists) if song.artists else None,
            duration=song.duration,
            thumbnail=song.cover_url,
            formats=[format_obj],
            tags=song.genres or [],
            media_url=media_url,
            is_playlist=False,
        )

    def _parse_playlist(self, playlist: Any, url: str) -> MediaInfo:
        """Parse playlist. Resuelve el audio canción a canción."""
        entries = []
        for idx, song in enumerate(playlist.songs or [], 1):
            # Una canción que no aparezca en ninguna fuente no debe tirar la lista
            media_url = self._resolve_media_url(song)
            if not media_url:
                console.print(f"[yellow]⚠️  Sin audio para {song.name!r}; se omite[/yellow]")
                continue

            format_obj = _audio_format()
            entries.append(
                PlaylistEntry(
                    id=song.song_id or f"track_{idx}",
                    title=song.name,
                    url=f"https://open.spotify.com/track/{song.song_id}" if song.song_id else url,
                    media_url=media_url,
                    duration=song.duration,
                    thumbnail=song.cover_url,
                    uploader=", ".join(song.artists) if song.artists else None,
                    index=idx,
                    formats=[format_obj],
                )
            )

        return MediaInfo(
            id=playlist.id or "",
            title=playlist.name,
            url=url,
            platform="Spotify",
            uploader=playlist.owner or None,
            duration=sum(s.duration or 0 for s in playlist.songs or []),
            thumbnail=playlist.cover_url,
            formats=[],
            is_playlist=True,
            playlist_title=playlist.name,
            playlist_id=playlist.id,
            playlist_uploader=playlist.owner,
            playlist_count=len(entries),
            entries=entries,
        )

    def _parse_album(self, album: Any, url: str) -> MediaInfo:
        """Parse album."""
        entries = []
        for idx, song in enumerate(album.songs or [], 1):
            media_url = self._resolve_media_url(song)
            if not media_url:
                console.print(f"[yellow]⚠️  Sin audio para {song.name!r}; se omite[/yellow]")
                continue

            format_obj = _audio_format()
            entries.append(
                PlaylistEntry(
                    id=song.song_id or f"track_{idx}",
                    title=song.name,
                    url=f"https://open.spotify.com/track/{song.song_id}" if song.song_id else url,
                    media_url=media_url,
                    duration=song.duration,
                    thumbnail=song.cover_url,
                    uploader=", ".join(song.artists) if song.artists else None,
                    index=idx,
                    formats=[format_obj],
                )
            )

        return MediaInfo(
            id=album.id or "",
            title=album.name,
            url=url,
            platform="Spotify",
            uploader=", ".join(album.artists) if album.artists else None,
            duration=sum(s.duration or 0 for s in album.songs or []),
            thumbnail=album.cover_url,
            formats=[],
            is_playlist=True,
            playlist_title=album.name,
            playlist_id=album.id,
            playlist_uploader=", ".join(album.artists) if album.artists else None,
            playlist_count=len(entries),
            entries=entries,
        )


console = get_console()
