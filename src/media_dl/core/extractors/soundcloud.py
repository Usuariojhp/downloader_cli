"""SoundCloud extractor using scdl (lazy loaded)."""

from __future__ import annotations

import asyncio
import json
import subprocess
from typing import Any, ClassVar

from media_dl.core.exceptions import ExtractorError
from media_dl.core.extractors.base import Extractor, register_extractor
from media_dl.core.models import Format, MediaInfo, PlaylistEntry

_scdl_available: bool | None = None


def check_scdl() -> bool:
    """Check if scdl is available."""
    global _scdl_available
    if _scdl_available is None:
        try:
            # Check if scdl command exists
            result = subprocess.run(["scdl", "--version"], capture_output=True, check=False)
            _scdl_available = result.returncode == 0
        except FileNotFoundError:
            _scdl_available = False
    return _scdl_available


@register_extractor
class SoundCloudExtractor(Extractor):
    """SoundCloud extractor using scdl CLI."""

    name = "soundcloud"
    domains: ClassVar[list[str]] = ["soundcloud.com", "m.soundcloud.com"]
    priority = 90

    def can_handle(self, url: str) -> bool:
        return super().can_handle(url) and check_scdl()

    async def extract(self, url: str) -> MediaInfo:
        """Extract SoundCloud track/playlist info via scdl."""
        self.validate_url(url)

        if not check_scdl():
            raise ExtractorError(
                "scdl not installed. Install with: pip install 'media-dl[soundcloud]'",
                url=url,
                platform="SoundCloud",
            )

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, self._extract_sync, url)

        return info

    def _extract_sync(self, url: str) -> MediaInfo:
        """Synchronous extraction using scdl CLI."""
        try:
            # Use scdl to get info as JSON
            result = subprocess.run(
                ["scdl", "-l", url, "--json", "--no-download"],
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )

            if result.returncode != 0:
                raise ExtractorError(
                    f"scdl failed: {result.stderr}", url=url, platform="SoundCloud"
                )

            # Parse JSON output
            tracks = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    try:
                        tracks.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            if not tracks:
                raise ExtractorError("No tracks found", url=url, platform="SoundCloud")

            # Check if it's a playlist/album
            if len(tracks) > 1 or "playlist" in url.lower() or "sets" in url.lower():
                return self._parse_playlist(tracks, url)
            else:
                return self._parse_track(tracks[0], url)

        except subprocess.TimeoutExpired as e:
            raise ExtractorError("scdl timed out", url=url, platform="SoundCloud") from e
        except Exception as e:
            raise ExtractorError(
                f"SoundCloud extraction failed: {e}", url=url, platform="SoundCloud", cause=e
            ) from e

    def _parse_track(self, track: dict[str, Any], url: str) -> MediaInfo:
        """Parse single track."""
        format_obj = Format(
            format_id="soundcloud_best",
            ext="mp3",
            vcodec="none",
            acodec="mp3",
            abr=320,
            quality_note="320kbps MP3",
        )

        return MediaInfo(
            id=str(track.get("id", "")),
            title=track.get("title", "Unknown"),
            url=url,
            platform="SoundCloud",
            uploader=track.get("user", {}).get("username"),
            duration=track.get("duration", 0) // 1000 if track.get("duration") else None,
            thumbnail=track.get("artwork_url") or track.get("user", {}).get("avatar_url"),
            formats=[format_obj],
            tags=track.get("genre", "").split(",") if track.get("genre") else [],
            is_playlist=False,
        )

    def _parse_playlist(self, tracks: list[Any], url: str) -> MediaInfo:
        """Parse playlist/set."""
        entries = []
        total_duration = 0

        for idx, track in enumerate(tracks, 1):
            format_obj = Format(
                format_id="soundcloud_best",
                ext="mp3",
                vcodec="none",
                acodec="mp3",
                abr=320,
                quality_note="320kbps MP3",
            )
            duration = track.get("duration", 0) // 1000 if track.get("duration") else None
            if duration:
                total_duration += duration

            entries.append(
                PlaylistEntry(
                    id=str(track.get("id", f"track_{idx}")),
                    title=track.get("title", "Unknown"),
                    url=track.get("permalink_url") or url,
                    duration=duration,
                    thumbnail=track.get("artwork_url") or track.get("user", {}).get("avatar_url"),
                    uploader=track.get("user", {}).get("username"),
                    index=idx,
                    formats=[format_obj],
                )
            )

        first_track = tracks[0] if tracks else {}
        return MediaInfo(
            id=str(first_track.get("playlist_id", first_track.get("id", ""))),
            title=first_track.get("playlist_title")
            or first_track.get("title", "SoundCloud Playlist"),
            url=url,
            platform="SoundCloud",
            uploader=first_track.get("user", {}).get("username"),
            duration=total_duration,
            thumbnail=first_track.get("artwork_url"),
            formats=[],
            is_playlist=True,
            playlist_title=first_track.get("playlist_title"),
            playlist_id=str(first_track.get("playlist_id", "")),
            playlist_uploader=first_track.get("user", {}).get("username"),
            playlist_count=len(entries),
            entries=entries,
        )
