"""Core package exports."""

from media_dl.core.exceptions import (
    ConfigurationError,
    DownloadError,
    DuplicateDownloadError,
    ExtractorError,
    HistoryError,
    MediaDLError,
    PlatformNotSupportedError,
    StrategyError,
    ValidationError,
)
from media_dl.core.models import (
    DownloadRequest,
    DownloadResult,
    Format,
    MediaInfo,
    PlaylistEntry,
    Thumbnail,
)

__all__ = [
    "ConfigurationError",
    "DownloadError",
    "DownloadRequest",
    "DownloadResult",
    "DuplicateDownloadError",
    "ExtractorError",
    "Format",
    "HistoryError",
    "MediaDLError",
    "MediaInfo",
    "PlatformNotSupportedError",
    "PlaylistEntry",
    "StrategyError",
    "Thumbnail",
    "ValidationError",
]
