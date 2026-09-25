"""Base extractor classes and registry."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import ClassVar
from urllib.parse import urlparse

from media_dl.core.exceptions import ValidationError
from media_dl.core.models import MediaInfo


class Extractor(ABC):
    """Abstract base class for media extractors."""

    name: str = "base"
    domains: ClassVar[list[str]] = []
    priority: int = 0  # Higher = more preferred

    def __init__(self) -> None:
        self._domain_patterns = [
            re.compile(d.replace(".", r"\.").replace("*", ".*")) for d in self.domains
        ]

    @abstractmethod
    async def extract(self, url: str) -> MediaInfo:
        """Extract media information from URL."""

    def can_handle(self, url: str) -> bool:
        """Check if this extractor can handle the given URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")
            return any(pattern.match(domain) for pattern in self._domain_patterns)
        except Exception:
            return False

    def validate_url(self, url: str) -> None:
        """Validate URL format."""
        if not url or not url.strip():
            raise ValidationError("URL cannot be empty", field="url", value=url)
        try:
            result = urlparse(url.strip())
            if not all([result.scheme, result.netloc]):
                raise ValueError
        except Exception as e:
            raise ValidationError("Invalid URL format", field="url", value=url) from e


def _builtin_extractors() -> list[type[Extractor]]:
    """Return the extractor classes shipped with media-dl (imported lazily)."""
    from media_dl.core.extractors.soundcloud import SoundCloudExtractor
    from media_dl.core.extractors.spotify import SpotifyExtractor
    from media_dl.core.extractors.tiktok_tikwn import TikTokTikwnExtractor
    from media_dl.core.extractors.ytdlp import YTDLPExtractor

    return [YTDLPExtractor, TikTokTikwnExtractor, SpotifyExtractor, SoundCloudExtractor]


class ExtractorRegistry:
    """Registry for managing extractors with priority ordering."""

    def __init__(self, auto_register: bool = True):
        self._extractors: list[type[Extractor]] = []
        if auto_register:
            self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        """Register the built-in extractors once (idempotent)."""
        if self._extractors:
            return
        for extractor_cls in _builtin_extractors():
            self.register(extractor_cls)

    def register(self, extractor_cls: type[Extractor]) -> type[Extractor]:
        """Register an extractor class."""
        if extractor_cls not in self._extractors:
            self._extractors.append(extractor_cls)
            self._extractors.sort(key=lambda x: x.priority, reverse=True)
        return extractor_cls

    def get_extractor(self, url: str) -> Extractor:
        """Get the best extractor for a URL."""
        self._ensure_defaults()

        for extractor_cls in self._extractors:
            instance = extractor_cls()
            if instance.can_handle(url):
                return instance

        # Fallback to generic extractor
        from media_dl.core.extractors.ytdlp import YTDLPExtractor

        return YTDLPExtractor()

    def get_all_extractors(self) -> list[Extractor]:
        """Get all registered extractor instances."""
        self._ensure_defaults()
        return [cls() for cls in self._extractors]


# Global registry instance. Built-ins are loaded lazily on first use to avoid
# a circular import (the extractor modules import register_extractor from here).
registry = ExtractorRegistry(auto_register=False)


def register_extractor(cls: type[Extractor]) -> type[Extractor]:
    """Decorator to register an extractor."""
    return registry.register(cls)


def get_extractor(url: str) -> Extractor:
    """Get extractor for URL."""
    instance = registry.get_extractor(url)
    instance.validate_url(url)
    return instance
