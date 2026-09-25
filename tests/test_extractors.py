"""Tests for extractors."""

import pytest

from media_dl.core.exceptions import ValidationError
from media_dl.core.extractors import (
    TikTokTikwnExtractor,
    YTDLPExtractor,
    get_extractor,
)
from media_dl.core.extractors.base import ExtractorRegistry


class TestYTDLPExtractor:
    def test_can_handle_youtube(self):
        extractor = YTDLPExtractor()
        assert extractor.can_handle("https://youtube.com/watch?v=test")
        assert extractor.can_handle("https://youtu.be/test")
        assert extractor.can_handle("https://www.youtube.com/watch?v=test")

    def test_can_handle_instagram(self):
        extractor = YTDLPExtractor()
        assert extractor.can_handle("https://instagram.com/p/test")

    def test_can_handle_twitter(self):
        extractor = YTDLPExtractor()
        assert extractor.can_handle("https://twitter.com/user/status/123")
        assert extractor.can_handle("https://x.com/user/status/123")

    def test_can_handle_tiktok(self):
        extractor = YTDLPExtractor()
        assert extractor.can_handle("https://tiktok.com/@user/video/123")

    def test_validate_url_empty(self):
        extractor = YTDLPExtractor()
        with pytest.raises(ValidationError):
            extractor.validate_url("")

    def test_validate_url_invalid(self):
        extractor = YTDLPExtractor()
        with pytest.raises(ValidationError):
            extractor.validate_url("not-a-url")

    def test_validate_url_valid(self):
        extractor = YTDLPExtractor()
        # Should not raise
        extractor.validate_url("https://youtube.com/watch?v=test")


class TestTikTokTikwnExtractor:
    def test_priority(self):
        extractor = TikTokTikwnExtractor()
        assert extractor.priority == 100

    def test_can_handle_tiktok(self):
        extractor = TikTokTikwnExtractor()
        assert extractor.can_handle("https://tiktok.com/@user/video/123")
        assert extractor.can_handle("https://vm.tiktok.com/abc")
        assert extractor.can_handle("https://vt.tiktok.com/xyz")


class TestExtractorRegistry:
    def test_get_extractor_youtube(self):
        extractor = get_extractor("https://youtube.com/watch?v=test")
        assert isinstance(extractor, YTDLPExtractor)

    def test_get_extractor_tiktok(self):
        # TikTok should get tikwn extractor first due to priority
        extractor = get_extractor("https://tiktok.com/@user/video/123")
        assert isinstance(extractor, TikTokTikwnExtractor)

    def test_get_extractor_unknown(self):
        # Unknown domain falls back to yt-dlp
        extractor = get_extractor("https://unknown-site.com/video")
        assert isinstance(extractor, YTDLPExtractor)

    def test_registry_ordering(self):
        registry = ExtractorRegistry()
        # TikTok extractor should be first due to priority 100
        extractors = registry.get_all_extractors()
        assert isinstance(extractors[0], TikTokTikwnExtractor)
