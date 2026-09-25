"""Native yt-dlp download strategy."""

from typing import Any

from media_dl.config.settings import Settings
from media_dl.core.strategies.base import DownloadStrategy


class NativeStrategy(DownloadStrategy):
    """Native yt-dlp downloader (no external dependencies)."""

    name = "native"
    requires_external = False

    def is_available(self) -> bool:
        """Always available."""
        return True

    def build_args(self, settings: Settings) -> dict[str, Any]:
        """Build native downloader arguments."""
        # Native strategy doesn't need special args
        # yt-dlp handles downloading internally
        return {}

    def get_display_name(self) -> str:
        """Get display name."""
        return "Normal (yt-dlp nativo)"
