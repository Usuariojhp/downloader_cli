"""Custom exception hierarchy for media-dl."""

from typing import Any


class MediaDLError(Exception):
    """Base exception for all media-dl errors."""

    def __init__(self, message: str, *, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause


class ConfigurationError(MediaDLError):
    """Configuration-related errors."""


class ExtractorError(MediaDLError):
    """Errors during media extraction."""

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        platform: str | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, cause=cause)
        self.url = url
        self.platform = platform


class DownloadError(MediaDLError):
    """Errors during download."""

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        filepath: str | None = None,
        strategy: str | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, cause=cause)
        self.url = url
        self.filepath = filepath
        self.strategy = strategy


class StrategyError(MediaDLError):
    """Errors related to download strategies."""

    def __init__(
        self,
        message: str,
        *,
        strategy: str | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, cause=cause)
        self.strategy = strategy


class HistoryError(MediaDLError):
    """Database/history errors."""


class ValidationError(MediaDLError):
    """Input validation errors."""

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        value: str | None = None,
    ):
        super().__init__(message)
        self.field = field
        self.value = value


class PlatformNotSupportedError(ExtractorError):
    """Raised when platform is not supported."""


class DuplicateDownloadError(DownloadError):
    """Raised when duplicate download is detected."""

    def __init__(self, message: str, *, existing_path: str, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.existing_path = existing_path
