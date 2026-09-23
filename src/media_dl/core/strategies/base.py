"""Download strategy base class and factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any
import shutil

from media_dl.config.settings import Settings
from media_dl.core.exceptions import StrategyError


class DownloadStrategy(ABC):
    """Abstract base class for download strategies."""

    name: str = "base"
    requires_external: bool = False

    @abstractmethod
    def build_args(self, settings: Settings) -> Dict[str, Any]:
        """Build yt-dlp options for this strategy."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if strategy is available on system."""
        pass

    def prepare(self, settings: Settings) -> None:
        """Optional preparation before download."""
        pass


class StrategyFactory:
    """Factory for creating download strategies."""

    _strategies: Dict[str, DownloadStrategy] = {}

    @classmethod
    def register(cls, strategy: DownloadStrategy) -> None:
        """Register a strategy."""
        cls._strategies[strategy.name] = strategy

    @classmethod
    def get(cls, name: str) -> DownloadStrategy:
        """Get strategy by name."""
        if name not in cls._strategies:
            raise StrategyError(f"Unknown strategy: {name}")
        return cls._strategies[name]

    @classmethod
    def get_best_available(cls, settings: Settings) -> DownloadStrategy:
        """Get the best available strategy based on settings."""
        preferred = settings.download_mode

        if preferred == "ultra":
            aria2c = cls._strategies.get("aria2c")
            if aria2c and aria2c.is_available():
                return aria2c

        # Fallback to native
        native = cls._strategies.get("native")
        if native:
            return native

        raise StrategyError("No download strategy available")


def build_strategy_args(strategy: DownloadStrategy, settings: Settings) -> Dict[str, Any]:
    """Build strategy args with common settings."""
    args = strategy.build_args(settings)

    # Add common options
    if settings.embed_thumbnail:
        args.setdefault("postprocessors", []).append({
            "key": "EmbedThumbnail",
            "already_have_thumbnail": False,
        })

    if settings.embed_metadata:
        args.setdefault("postprocessors", []).append({
            "key": "FFmpegMetadata",
        })

    if settings.write_info_json:
        args["writeinfojson"] = True

    return args