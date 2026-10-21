"""Extractors package exports."""

from veluz.core.extractors.base import (
    Extractor,
    ExtractorRegistry,
    get_extractor,
    register_extractor,
    registry,
)
from veluz.core.extractors.soundcloud import SoundCloudExtractor
from veluz.core.extractors.spotify import SpotifyExtractor
from veluz.core.extractors.tiktok_tikwn import TikTokTikwnExtractor
from veluz.core.extractors.ytdlp import YTDLPExtractor, extract_with_ytdlp

__all__ = [
    "Extractor",
    "ExtractorRegistry",
    "SoundCloudExtractor",
    "SpotifyExtractor",
    "TikTokTikwnExtractor",
    "YTDLPExtractor",
    "extract_with_ytdlp",
    "get_extractor",
    "register_extractor",
    "registry",
]
