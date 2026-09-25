"""Tests for core models."""

from media_dl.core.models import (
    DownloadRequest,
    DownloadResult,
    Format,
    MediaInfo,
    PlaylistEntry,
)


class TestFormat:
    def test_format_properties(self):
        fmt = Format(
            format_id="137",
            ext="mp4",
            resolution="1080p",
            height=1080,
            vcodec="avc1",
            acodec="mp4a",
            filesize=50000000,
            tbr=5000,
            quality_note="1080p",
        )
        assert fmt.is_video is True
        assert fmt.is_audio is False
        assert "1080p" in fmt.display_name

    def test_audio_format(self):
        fmt = Format(
            format_id="140",
            ext="m4a",
            vcodec="none",
            acodec="mp4a",
            filesize=5000000,
            abr=128,
        )
        assert fmt.is_video is False
        assert fmt.is_audio is True


class TestDuration:
    """Regresión: yt-dlp devuelve duraciones decimales (Facebook, reels...) y el
    modelo las rechazaba con ValidationError, rompiendo la descarga entera."""

    def test_media_info_accepts_float_duration(self):
        info = MediaInfo(id="x", title="t", url="u", platform="Facebook", duration=74.304)
        assert info.duration == 74.304

    def test_duration_str_truncates(self):
        info = MediaInfo(id="x", title="t", url="u", platform="p", duration=74.304)
        assert info.duration_str == "1m 14s"

    def test_playlist_entry_accepts_float_duration(self):
        entry = PlaylistEntry(id="1", title="t", url="u", duration=90.75)
        assert entry.duration == 90.75

    def test_format_duration_accepts_float(self):
        from media_dl.ui.tables import format_duration

        assert format_duration(90.75) == "1m 30s"
        assert format_duration(74.304) == "1m 14s"


class TestPlaylistEntry:
    def test_playlist_entry_ordering(self):
        entry1 = PlaylistEntry(id="1", title="A", url="u1", index=2)
        entry2 = PlaylistEntry(id="2", title="B", url="u2", index=1)
        assert entry2 < entry1  # index 1 < index 2


class TestMediaInfo:
    def test_available_heights(self, sample_media_info):
        heights = sample_media_info.available_heights
        assert 1080 in heights

    def test_best_video_format(self, sample_media_info):
        best = sample_media_info.best_video_format
        assert best is not None
        assert best.height == 1080

    def test_best_audio_format(self, sample_media_info):
        best = sample_media_info.best_audio_format
        assert best is not None
        assert best.abr == 128

    def test_duration_str(self, sample_media_info):
        assert sample_media_info.duration_str == "5m 0s"

    def test_playlist_properties(self, sample_playlist_info):
        assert sample_playlist_info.is_playlist is True
        assert len(sample_playlist_info.entries) == 3
        assert sample_playlist_info.playlist_count == 3


class TestDownloadRequest:
    def test_defaults(self):
        req = DownloadRequest(url="https://test.com/video")
        assert req.media_type == "video"
        assert req.format == "mp3"
        assert req.bitrate == 192
        assert req.strategy == "ultra"

    def test_audio_request(self):
        req = DownloadRequest(
            url="https://test.com/video",
            media_type="audio",
            format="mp3",
            bitrate=320,
        )
        assert req.media_type == "audio"
        assert req.bitrate == 320


class TestDownloadResult:
    def test_success_result(self):
        result = DownloadResult(
            success=True,
            message="OK",
            filepath="/tmp/video.mp4",
            filesize=1000000,
            duration=5.5,
        )
        assert result.success is True
        assert result.error is None

    def test_error_result(self):
        result = DownloadResult(
            success=False,
            message="Failed",
            error="Network error",
        )
        assert result.success is False
        assert result.error == "Network error"
