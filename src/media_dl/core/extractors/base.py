"""Base extractor classes and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Type, Optional
from urllib.parse import urlparse
import re

from media_dl.core.models import MediaInfo
from media_dl.core.exceptions import ExtractorError, PlatformNotSupportedError


class Extractor(ABC):
    """Abstract base class for media extractors."""

    name: str = "base"
    domains: List[str] = []
    priority: int = 0  # Higher = more preferred

    def __init__(self):
        self._domain_patterns = [re.compile(d.replace(".", r"\.").replace("*", ".*")) for d in self.domains]

    @abstractmethod
    async def extract(self, url: str) -> MediaInfo:
        """Extract media information from URL."""
        pass

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
        except Exception:
            raise ValidationError("Invalid URL format", field="url", value=url)


class ExtractorRegistry:
    """Registry for managing extractors with priority ordering."""

    def __init__(self):
        self._extractors: List[Type[Extractor]] = []

    def register(self, extractor_cls: Type[Extractor]) -> Type[Extractor]:
        """Register an extractor class."""
        if extractor_cls not in self._extractors:
            self._extractors.append(extractor_cls)
            self._extractors.sort(key=lambda x: x.priority, reverse=True)
        return extractor_cls

    def get_extractor(self, url: str) -> Extractor:
        """Get the best extractor for a URL."""
        for extractor_cls in self._extractors:
            instance = extractor_cls()
            if instance.can_handle(url):
                return instance
        # Fallback to generic extractor
        from media_dl.core.extractors.ytdlp import YTDLPExtractor
        return YTDLPExtractor()

    def get_all_extractors(self) -> List[Extractor]:
        """Get all registered extractor instances."""
        return [cls() for cls in self._extractors]


# Global registry instance
registry = ExtractorRegistry()


def register_extractor(cls: Type[Extractor]) -> Type[Extractor]:
    """Decorator to register an extractor."""
    return registry.register(cls)


def get_extractor(url: str) -> Extractor:
    """Get extractor for URL."""
    return registry.get_extractor(url)