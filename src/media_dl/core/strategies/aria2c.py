"""Aria2c ultra-fast download strategy."""

import shutil
from typing import Any

from media_dl.config.settings import Settings
from media_dl.core.strategies.base import DownloadStrategy


class Aria2cStrategy(DownloadStrategy):
    """Ultra-fast download using aria2c with multiple connections."""

    name = "aria2c"
    requires_external = True

    def is_available(self) -> bool:
        """Check if aria2c is installed."""
        return shutil.which("aria2c") is not None

    def build_args(self, settings: Settings) -> dict[str, Any]:
        """Build aria2c arguments."""
        connections = min(settings.aria2c_connections, 16)
        split = min(settings.aria2c_split, 16)

        aria2c_args = [
            f"-x{connections}",
            f"-s{split}",
            "-k1M",
            "--min-split-size=1M",
            "--file-allocation=none",
            "--max-connection-per-server=16",
            "--split=16",
            "--allow-overwrite=true",
            "--auto-file-renaming=false",
        ]

        if settings.max_download_speed > 0:
            aria2c_args.append(f"--max-download-limit={settings.max_download_speed}K")

        return {
            "external_downloader": "aria2c",
            "external_downloader_args": {"aria2c": aria2c_args},
        }

    def get_display_name(self, settings: Settings) -> str:
        """Get display name with connection count."""
        return f"ULTRA RÁPIDO (Aria2c - {settings.aria2c_connections} hilos)"
