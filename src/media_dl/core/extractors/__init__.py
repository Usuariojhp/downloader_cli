"""Extractors package exports."""

from media_dl.core.extractors.base import (
    Extractor,
    ExtractorRegistry,
    get_extractor,
    register_extractor,
    registry,
)
from media_dl.core.extractors.soundcloud import SoundCloudExtractor
from media_dl.core.extractors.spotify import SpotifyExtractor
from media_dl.core.extractors.tiktok_tikwn import TikTokTikwnExtractor
from media_dl.core.extractors.ytdlp import YTDLPExtractor, extract_with_ytdlp

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
