"""TikTok fallback extractor using tikwn.com API."""

from __future__ import annotations

from types import TracebackType
from typing import ClassVar

import httpx

from media_dl.core.exceptions import ExtractorError
from media_dl.core.extractors.base import Extractor, register_extractor
from media_dl.core.models import Format, MediaInfo
from media_dl.ui.console import get_console


@register_extractor
class TikTokTikwnExtractor(Extractor):
    """TikTok extractor using tikwn.com API as fallback."""

    name = "tiktok-tikwn"
    domains: ClassVar[list[str]] = ["tiktok.com", "vm.tiktok.com", "vt.tiktok.com"]
    priority = 100  # High priority for TikTok specifically
    #: La API de terceros puede desaparecer o caerse; en ese caso se usa yt-dlp.
    fallback_to_ytdlp = True

    def __init__(self) -> None:
        super().__init__()
        self.api_url = "https://www.tikwn.com/api/"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=30.0)

    async def extract(self, url: str) -> MediaInfo:
        """Extract TikTok video info via tikwn.com API, falling back to yt-dlp."""
        self.validate_url(url)

        try:
            return await self._extract_via_api(url)
        except ExtractorError as e:
            if not self.fallback_to_ytdlp:
                raise
            console = get_console()
            console.print(f"[yellow]⚠️  {self.name} no disponible ({e}); usando yt-dlp[/yellow]")
            from media_dl.core.extractors.ytdlp import YTDLPExtractor

            return await YTDLPExtractor().extract(url)

    async def _extract_via_api(self, url: str) -> MediaInfo:
        """Query the third-party API for direct media URLs."""
        try:
            data = {"url": url, "hd": "1"}
            response = await self.client.post(self.api_url, data=data)
            response.raise_for_status()
            result = response.json()

            if result.get("code") != 0:
                raise ExtractorError(
                    f"Tikwn API error: {result.get('msg', 'Unknown error')}",
                    url=url,
                    platform="TikTok",
                )

            data = result["data"]
            play_url = data.get("play", "")

            # Build video URL
            if play_url and not play_url.startswith("http"):
                video_url = f"https://www.tikwn.com{play_url}"
            else:
                video_url = play_url

            if not video_url:
                raise ExtractorError("No play URL in response", url=url, platform="TikTok")

            # Create format
            format_obj = Format(
                format_id="tikwn_hd" if data.get("hd") == "1" else "tikwn_sd",
                ext="mp4",
                resolution="720p" if data.get("hd") == "1" else "480p",
                vcodec="h264",
                acodec="aac",
                quality_note="HD" if data.get("hd") == "1" else "SD",
                protocol="https",
            )

            return MediaInfo(
                id=data.get("id", ""),
                title=data.get("title") or f"TikTok_{data.get('id', 'unknown')}",
                url=url,
                platform="TikTok",
                uploader=data.get("author", {}).get("nickname"),
                duration=data.get("duration"),
                thumbnail=data.get("cover"),
                formats=[format_obj],
                is_playlist=False,
            )

        except httpx.HTTPError as e:
            raise ExtractorError(f"HTTP error: {e}", url=url, platform="TikTok", cause=e) from e
        except Exception as e:
            raise ExtractorError(
                f"Tikwn extraction failed: {e}", url=url, platform="TikTok", cause=e
            ) from e

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> TikTokTikwnExtractor:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()
