"""SoundCloud extractor (delegated to yt-dlp).

yt-dlp soporta SoundCloud de forma nativa y devuelve los formats reales
(mp3/hls y, cuando el artista lo habilitó, la descarga original).  La ruta
antigua con ``scdl`` invocaba un modo JSON (``--json --no-download``) que su
CLI no expone, así que toda extracción fallaba; ``check_scdl`` se conserva
solo por compatibilidad con el extra ``veluz[soundcloud]``.
"""

from __future__ import annotations

import subprocess
from typing import ClassVar

from veluz.core.extractors.base import Extractor, register_extractor
from veluz.core.models import MediaInfo

_scdl_available: bool | None = None


def check_scdl() -> bool:
    """Return True si el CLI heredado ``scdl`` está instalado (informativo)."""
    global _scdl_available
    if _scdl_available is None:
        try:
            result = subprocess.run(["scdl", "--version"], capture_output=True, check=False)
            _scdl_available = result.returncode == 0
        except FileNotFoundError:
            _scdl_available = False
    return _scdl_available


@register_extractor
class SoundCloudExtractor(Extractor):
    """SoundCloud extractor backed by yt-dlp."""

    name = "soundcloud"
    domains: ClassVar[list[str]] = ["soundcloud.com", "m.soundcloud.com"]
    priority = 90

    async def extract(self, url: str) -> MediaInfo:
        """Extract track/playlist info via yt-dlp."""
        self.validate_url(url)

        from veluz.core.extractors.ytdlp import YTDLPExtractor

        return await YTDLPExtractor().extract(url)
