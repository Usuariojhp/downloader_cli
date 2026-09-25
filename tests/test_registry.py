"""Tests for the extractor registry and URL validation."""

import pytest

from media_dl.core.exceptions import ValidationError
from media_dl.core.extractors import (
    SoundCloudExtractor,
    SpotifyExtractor,
    TikTokTikwnExtractor,
    YTDLPExtractor,
    get_extractor,
)
from media_dl.core.extractors.base import ExtractorRegistry


class TestRegistryDefaults:
    def test_fresh_registry_has_builtins(self):
        extractors = ExtractorRegistry().get_all_extractors()
        names = [type(e).__name__ for e in extractors]

        assert "YTDLPExtractor" in names
        assert len(names) == 4

    def test_sorted_by_priority(self):
        extractors = ExtractorRegistry().get_all_extractors()
        priorities = [e.priority for e in extractors]

        assert priorities == sorted(priorities, reverse=True)
        assert isinstance(extractors[0], TikTokTikwnExtractor)

    def test_no_duplicate_instances(self):
        registry = ExtractorRegistry()
        assert len(registry.get_all_extractors()) == len(registry.get_all_extractors())

    def test_ensure_defaults_is_idempotent(self):
        registry = ExtractorRegistry()
        first = registry.get_all_extractors()
        registry._ensure_defaults()

        assert len(registry.get_all_extractors()) == len(first)

    def test_explicit_empty_registry(self):
        assert ExtractorRegistry(auto_register=False).get_all_extractors() != []


class TestSelection:
    def test_youtube(self):
        assert isinstance(get_extractor("https://youtube.com/watch?v=x"), YTDLPExtractor)

    def test_tiktok_prefers_tikwn(self):
        assert isinstance(get_extractor("https://tiktok.com/@u/video/1"), TikTokTikwnExtractor)

    def test_spotify(self):
        assert isinstance(get_extractor("https://open.spotify.com/track/1"), SpotifyExtractor)

    def test_soundcloud(self):
        assert isinstance(get_extractor("https://soundcloud.com/u/t"), SoundCloudExtractor)

    def test_unknown_falls_back_to_ytdlp(self):
        assert isinstance(get_extractor("https://example.com/v"), YTDLPExtractor)


class TestUrlValidation:
    @pytest.mark.parametrize("url", ["", "   ", None])
    def test_rejects_empty(self, url):
        with pytest.raises(ValidationError):
            get_extractor(url)

    @pytest.mark.parametrize("url", ["not-a-url", "youtube.com/watch", "http://"])
    def test_rejects_malformed(self, url):
        with pytest.raises(ValidationError):
            get_extractor(url)

    def test_accepts_valid(self):
        assert get_extractor("https://youtube.com/watch?v=x") is not None

    def test_error_carries_context(self):
        with pytest.raises(ValidationError) as exc:
            get_extractor("")

        assert exc.value.field == "url"
