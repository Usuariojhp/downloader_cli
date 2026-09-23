"""Spotify extractor using spotdl (lazy loaded)."""

from __future__ import annotations

from typing import Optional, List
import asyncio

from media_dl.core.extractors.base import Extractor, register_extractor
from media_dl.core.models import MediaInfo, Format, PlaylistEntry
from media_dl.core.exceptions import ExtractorError


_spotdl_available: Optional[bool] = None


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


@register_extractor
class SpotifyExtractor(Extractor):
    """Spotify extractor using spotdl."""

    name = "spotify"
    domains = ["open.spotify.com", "spotify.com"]
    priority = 90

    def __init__(self):
        super().__init__()
        self._spotdl = None
        self._downloader = None

    def _ensure_spotdl(self):
        """Lazy import and initialize spotdl."""
        if not check_spotdl():
            raise ExtractorError(
                "spotdl not installed. Install with: pip install 'media-dl[spotify]'",
                platform="Spotify",
            )
        if self._spotdl is None:
            from spotdl import Spotdl
            from spotdl.types.song import Song

            # Initialize with default settings
            self._spotdl = Spotdl(
                client_id="",
                client_secret="",
                user_auth=False,
                no_cache=True,
                headless=True,
            )

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
        from spotdl.types.song import Song
        from spotdl.types.playlist import Playlist
        from spotdl.types.album import Album

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
            raise ExtractorError(f"Spotify extraction failed: {e}", url=url, platform="Spotify", cause=e)

    def _parse_track(self, song, url: str) -> MediaInfo:
        """Parse single track."""
        format_obj = Format(
            format_id="spotify_best",
            ext="mp3",
            vcodec="none",
            acodec="mp3",
            abr=320,
            quality_note="320kbps MP3",
        )

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
            is_playlist=False,
        )

    def _parse_playlist(self, playlist, url: str) -> MediaInfo:
        """Parse playlist."""
        entries = []
        for idx, song in enumerate(playlist.songs or [], 1):
            format_obj = Format(
                format_id="spotify_best",
                ext="mp3",
                vcodec="none",
                acodec="mp3",
                abr=320,
                quality_note="320kbps MP3",
            )
            entries.append(PlaylistEntry(
                id=song.song_id or f"track_{idx}",
                title=song.name,
                url=f"https://open.spotify.com/track/{song.song_id}" if song.song_id else url,
                duration=song.duration,
                thumbnail=song.cover_url,
                uploader=", ".join(song.artists) if song.artists else None,
                index=idx,
                formats=[format_obj],
            ))

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

    def _parse_album(self, album, url: str) -> MediaInfo:
        """Parse album."""
        entries = []
        for idx, song in enumerate(album.songs or [], 1):
            format_obj = Format(
                format_id="spotify_best",
                ext="mp3",
                vcodec="none",
                acodec="mp3",
                abr=320,
                quality_note="320kbps MP3",
            )
            entries.append(PlaylistEntry(
                id=song.song_id or f"track_{idx}",
                title=song.name,
                url=f"https://open.spotify.com/track/{song.song_id}" if song.song_id else url,
                duration=song.duration,
                thumbnail=song.cover_url,
                uploader=", ".join(song.artists) if song.artists else None,
                index=idx,
                formats=[format_obj],
            ))

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