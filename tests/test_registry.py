"""Tests for the extractor registry and URL validation."""

from unittest.mock import AsyncMock, patch

import pytest

from media_dl.cli.commands.download import _run_async as _run
from media_dl.core.exceptions import ValidationError
from media_dl.core.extractors import (
    SoundCloudExtractor,
    SpotifyExtractor,
    TikTokTikwnExtractor,
    YTDLPExtractor,
    get_extractor,
)
from media_dl.core.extractors.base import ExtractorRegistry
from media_dl.core.models import MediaInfo


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

    def test_spotify_when_available(self):
        """spotdl es opcional: sin él, el registro cae en yt-dlp."""
        from media_dl.core.extractors.spotify import check_spotdl

        extractor = get_extractor("https://open.spotify.com/track/1")
        if check_spotdl():
            assert isinstance(extractor, SpotifyExtractor)
        else:
            assert isinstance(extractor, YTDLPExtractor)

    def test_soundcloud_when_available(self):
        """scdl es opcional: sin el binario, el registro cae en yt-dlp."""
        from media_dl.core.extractors.soundcloud import check_scdl

        extractor = get_extractor("https://soundcloud.com/u/t")
        if check_scdl():
            assert isinstance(extractor, SoundCloudExtractor)
        else:
            assert isinstance(extractor, YTDLPExtractor)

    def test_spotify_and_soundcloud_are_registered(self):
        """Aunque falte el extra, el extractor está registrado y con prioridad."""
        names = [type(e).__name__ for e in ExtractorRegistry().get_all_extractors()]

        assert "SpotifyExtractor" in names
        assert "SoundCloudExtractor" in names

    def test_unknown_falls_back_to_ytdlp(self):
        assert isinstance(get_extractor("https://example.com/v"), YTDLPExtractor)


class TestTikTokFallback:
    """El extractor de TikTok tiene prioridad 100: si su API third-party cae,
    debe degradar a yt-dlp en vez de romper la descarga."""

    def test_falls_back_to_ytdlp_on_api_error(self):
        from media_dl.core.exceptions import ExtractorError

        extractor = TikTokTikwnExtractor()
        url = "https://www.tiktok.com/@u/video/1"

        esperado = MediaInfo(id="1", title="vía yt-dlp", url=url, platform="TikTok")

        with (
            patch.object(
                TikTokTikwnExtractor, "_extract_via_api", side_effect=ExtractorError("API caida")
            ) as api,
            patch(
                "media_dl.core.extractors.ytdlp.YTDLPExtractor.extract",
                new=AsyncMock(return_value=esperado),
            ) as ytdlp,
        ):
            resultado = _run(extractor.extract(url))

        api.assert_called_once()
        ytdlp.assert_awaited_once_with(url)
        assert resultado is esperado

    def test_no_fallback_when_disabled(self):
        from media_dl.core.exceptions import ExtractorError

        extractor = TikTokTikwnExtractor()
        extractor.fallback_to_ytdlp = False

        with (
            patch.object(
                TikTokTikwnExtractor, "_extract_via_api", side_effect=ExtractorError("API caida")
            ),
            pytest.raises(ExtractorError),
        ):
            _run(extractor.extract("https://www.tiktok.com/@u/video/1"))

    def test_returns_api_result_when_available(self):
        extractor = TikTokTikwnExtractor()
        info = MediaInfo(id="1", title="t", url="u", platform="TikTok")

        with patch.object(TikTokTikwnExtractor, "_extract_via_api", return_value=info):
            assert _run(extractor.extract("https://www.tiktok.com/@u/video/1")) is info


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
