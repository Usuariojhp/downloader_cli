"""Extractors package exports."""

from media_dl.core.extractors.base import (
    Extractor,
    ExtractorRegistry,
    registry,
    register_extractor,
    get_extractor,
)
from media_dl.core.extractors.ytdlp import YTDLPExtractor, extract_with_ytdlp
from media_dl.core.extractors.tiktok_tikwn import TikTokTikwnExtractor
from media_dl.core.extractors.spotify import SpotifyExtractor
from media_dl.core.extractors.soundcloud import SoundCloudExtractor

__all__ = [
    "Extractor",
    "ExtractorRegistry",
    "registry",
    "register_extractor",
    "get_extractor",
    "YTDLPExtractor",
    "extract_with_ytdlp",
    "TikTokTikwnExtractor",
    "SpotifyExtractor",
    "SoundCloudExtractor",
]