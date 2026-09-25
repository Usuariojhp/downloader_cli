"""yt-dlp based extractor for YouTube, Instagram, Twitter, Facebook, TikTok, etc."""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar, cast

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError as YTDLPError

from media_dl.core.exceptions import ExtractorError
from media_dl.core.extractors.base import Extractor, register_extractor
from media_dl.core.models import Format, MediaInfo, PlaylistEntry, Thumbnail


@register_extractor
class YTDLPExtractor(Extractor):
    """Universal extractor using yt-dlp."""

    name = "yt-dlp"
    domains: ClassVar[list[str]] = [
        "youtube.com",
        "youtu.be",
        "instagram.com",
        "twitter.com",
        "x.com",
        "facebook.com",
        "fb.watch",
        "tiktok.com",
        "twitch.tv",
        "vimeo.com",
        "dailymotion.com",
        "soundcloud.com",
        "bandcamp.com",
        "rumble.com",
        "odysee.com",
        "bilibili.com",
        "nicovideo.jp",
    ]
    priority = 10

    def __init__(self) -> None:
        super().__init__()
        self._base_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
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
        }

    async def extract(self, url: str) -> MediaInfo:
        """Extract media info using yt-dlp."""
        self.validate_url(url)

        # Run yt-dlp in executor to avoid blocking
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, self._extract_sync, url)

        return self._parse_info(info, url)

    def _extract_sync(self, url: str) -> dict[str, Any]:
        """Synchronous extraction."""
        opts = {**self._base_opts}
        try:
            with YoutubeDL(opts) as ydl:  # type: ignore[no-untyped-call]
                return cast("dict[str, Any]", ydl.extract_info(url, download=False))
        except YTDLPError as e:
            raise ExtractorError(
                f"yt-dlp extraction failed: {e}", url=url, platform=self.name, cause=e
            ) from e
        except Exception as e:
            raise ExtractorError(
                f"Unexpected extraction error: {e}", url=url, platform=self.name, cause=e
            ) from e

    def _parse_info(self, info: dict[str, Any], original_url: str) -> MediaInfo:
        """Parse yt-dlp info dict to MediaInfo."""
        if not info:
            raise ExtractorError("No info extracted", url=original_url, platform=self.name)

        # Handle playlists
        is_playlist = bool(info.get("entries"))
        playlist_title = info.get("title") if is_playlist else None
        entries = (
            [
                self._parse_entry(entry, idx + 1)
                for idx, entry in enumerate(info["entries"] or [])
                if entry
            ]
            if is_playlist
            else []
        )

        # Parse formats and thumbnails
        formats = [self._parse_format(f) for f in info.get("formats") or []]
        thumbnails = [
            Thumbnail(
                url=t.get("url", ""),
                width=t.get("width"),
                height=t.get("height"),
                resolution=t.get("resolution"),
            )
            for t in info.get("thumbnails") or []
        ]

        return MediaInfo(
            id=info.get("id", ""),
            title=info.get("title", "Unknown"),
            url=original_url,
            platform=self._detect_platform(original_url),
            uploader=info.get("uploader"),
            uploader_id=info.get("uploader_id"),
            uploader_url=info.get("uploader_url"),
            duration=info.get("duration"),
            view_count=info.get("view_count"),
            like_count=info.get("like_count"),
            description=info.get("description"),
            thumbnail=info.get("thumbnail"),
            thumbnails=thumbnails,
            formats=formats,
            subtitles=info.get("subtitles", {}),
            automatic_captions=info.get("automatic_captions", {}),
            tags=info.get("tags") or [],
            categories=info.get("categories") or [],
            age_limit=info.get("age_limit"),
            is_live=info.get("is_live", False),
            was_live=info.get("was_live", False),
            availability=info.get("availability"),
            is_playlist=is_playlist,
            playlist_title=playlist_title,
            playlist_id=info.get("id") if is_playlist else None,
            playlist_uploader=info.get("uploader") if is_playlist else None,
            playlist_count=len(entries) if entries else info.get("playlist_count"),
            entries=entries,
        )

    def _parse_entry(self, entry: dict[str, Any], index: int) -> PlaylistEntry:
        """Parse playlist entry."""
        formats = [self._parse_format(f) for f in entry.get("formats") or []]

        return PlaylistEntry(
            id=entry.get("id", ""),
            title=entry.get("title", "Unknown"),
            url=entry.get("url")
            or entry.get("webpage_url")
            or f"https://www.youtube.com/watch?v={entry.get('id')}",
            duration=entry.get("duration"),
            thumbnail=entry.get("thumbnail"),
            uploader=entry.get("uploader"),
            index=index,
            formats=formats,
        )

    def _parse_format(self, f: dict[str, Any]) -> Format:
        """Parse format dict."""
        return Format(
            format_id=f.get("format_id", ""),
            ext=f.get("ext", ""),
            resolution=f.get("resolution"),
            fps=f.get("fps"),
            vcodec=f.get("vcodec"),
            acodec=f.get("acodec"),
            filesize=f.get("filesize"),
            filesize_approx=f.get("filesize_approx"),
            tbr=f.get("tbr"),
            vbr=f.get("vbr"),
            abr=f.get("abr"),
            quality_note=f.get("format_note") or f.get("quality_note"),
            protocol=f.get("protocol"),
            height=f.get("height"),
            width=f.get("width"),
        )

    def _detect_platform(self, url: str) -> str:
        """Detect platform from URL."""
        url_lower = url.lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "YouTube"
        elif "instagram.com" in url_lower:
            return "Instagram"
        elif "twitter.com" in url_lower or "x.com" in url_lower:
            return "Twitter/X"
        elif "facebook.com" in url_lower or "fb.watch" in url_lower:
            return "Facebook"
        elif "tiktok.com" in url_lower:
            return "TikTok"
        elif "twitch.tv" in url_lower:
            return "Twitch"
        elif "vimeo.com" in url_lower:
            return "Vimeo"
        elif "soundcloud.com" in url_lower:
            return "SoundCloud"
        else:
            return "Unknown"


# Convenience function
async def extract_with_ytdlp(url: str) -> MediaInfo:
    """Extract media info using yt-dlp."""
    extractor = YTDLPExtractor()
    return await extractor.extract(url)
