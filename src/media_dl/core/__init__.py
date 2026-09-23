"""Core package exports."""

from media_dl.core.models import (
    Format,
    Thumbnail,
    PlaylistEntry,
    MediaInfo,
    DownloadRequest,
    DownloadResult,
)
from media_dl.core.exceptions import (
    MediaDLError,
    ConfigurationError,
    ExtractorError,
    DownloadError,
    StrategyError,
    HistoryError,
    ValidationError,
    PlatformNotSupportedError,
    DuplicateDownloadError,
)

__all__ = [
    "Format",
    "Thumbnail",
    "PlaylistEntry",
    "MediaInfo",
    "DownloadRequest",
    "DownloadResult",
    "MediaDLError",
    "ConfigurationError",
    "ExtractorError",
    "DownloadError",
    "StrategyError",
    "HistoryError",
    "ValidationError",
    "PlatformNotSupportedError",
    "DuplicateDownloadError",
]