"""Tests for the playlist command."""

from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from media_dl.config import Settings
from media_dl.core.models import MediaInfo, PlaylistEntry


@pytest.fixture
def settings(tmp_path):
    return Settings(
        download_path=tmp_path / "downloads",
        config_dir=tmp_path / "config",
        db_path=tmp_path / "config" / "history.db",
    )


@pytest.fixture
def playlist_info():
    return MediaInfo(
        id="PL1",
        title="Mi playlist",
        url="https://youtube.com/playlist?list=PL1",
        platform="YouTube",
        is_playlist=True,
        playlist_title="Mi playlist",
        entries=[
            PlaylistEntry(
                id=f"v{i}",
                title=f"Video {i}",
                url=f"https://youtube.com/watch?v=v{i}",
                duration=100 * i,
                index=i,
            )
            for i in range(1, 6)
        ],
    )


def _patches(info, *, is_duplicate=None, download_result="/tmp/out.mp4"):
    """Patch every collaborator of the playlist command."""
    extractor = MagicMock()
    extractor.extract = MagicMock()

    repo = MagicMock()
    repo.is_duplicate.return_value = is_duplicate

    strategy = MagicMock()
    strategy.is_available.return_value = True
    strategy.build_args.return_value = {}

    return {
        "get_settings": patch("media_dl.cli.commands.playlist.get_settings"),
        "get_extractor": patch(
            "media_dl.cli.commands.playlist.get_extractor", return_value=extractor
        ),
        "repo": patch("media_dl.cli.commands.playlist.HistoryRepository", return_value=repo),
        "factory": patch(
            "media_dl.cli.commands.playlist.StrategyFactory.get", return_value=strategy
        ),
        "run_async": patch("media_dl.cli.commands.playlist._run_async", return_value=info),
        "download": patch(
            "media_dl.cli.commands.playlist._download_single", return_value=download_result
        ),
        "confirm": patch("media_dl.cli.commands.playlist.prompt_yes_no", return_value=True),
    }


def run_playlist(args, info, settings, **kwargs):
    patches = _patches(info, **kwargs)
    started = {}
    try:
        for name, patcher in patches.items():
            started[name] = patcher.start()
        # patcher.start() devuelve el mock de la clase; el repo es su instancia
        started["repo"] = started["repo"].return_value
        started["get_settings"].return_value = settings
        from media_dl.main import app

        return CliRunner().invoke(app, args), started
    finally:
        for patcher in patches.values():
            patcher.stop()


class TestValidation:
    def test_rejects_unknown_type(self, settings):
        from media_dl.cli.commands.playlist import playlist

        with (
            patch("media_dl.cli.commands.playlist.get_settings", return_value=settings),
            pytest.raises(typer.Exit),
        ):
            playlist(ctx=None, url="u", media_type="pelicula")

    def test_rejects_unknown_format(self, settings):
        from media_dl.cli.commands.playlist import playlist

        with (
            patch("media_dl.cli.commands.playlist.get_settings", return_value=settings),
            pytest.raises(typer.Exit),
        ):
            playlist(ctx=None, url="u", audio_format="ogg")

    def test_rejects_bad_bitrate(self, settings):
        from media_dl.cli.commands.playlist import playlist

        with (
            patch("media_dl.cli.commands.playlist.get_settings", return_value=settings),
            pytest.raises(typer.Exit),
        ):
            playlist(ctx=None, url="u", media_type="audio", bitrate=999)


class TestSelection:
    def test_downloads_everything_by_default(self, playlist_info, settings):
        _, mocks = run_playlist(["playlist", playlist_info.url], playlist_info, settings)
        assert mocks["download"].call_count == 5

    def test_range_limits_entries(self, playlist_info, settings):
        _, mocks = run_playlist(
            ["playlist", playlist_info.url, "--range", "1-2"], playlist_info, settings
        )
        assert mocks["download"].call_count == 2

    def test_range_all_means_everything(self, playlist_info, settings):
        _, mocks = run_playlist(
            ["playlist", playlist_info.url, "--range", "all"], playlist_info, settings
        )
        assert mocks["download"].call_count == 5

    def test_invalid_range_aborts(self, playlist_info, settings):
        from media_dl.cli.commands.playlist import playlist

        with (
            patch("media_dl.cli.commands.playlist.get_settings", return_value=settings),
            patch("media_dl.cli.commands.playlist.get_extractor"),
            patch("media_dl.cli.commands.playlist._run_async", return_value=playlist_info),
            patch("media_dl.cli.commands.playlist.prompt_yes_no", return_value=True),
            pytest.raises(typer.Exit),
        ):
            playlist(ctx=None, url=playlist_info.url, range="9-3")

    def test_declining_confirmation_cancels(self, playlist_info, settings):
        patches = _patches(playlist_info)
        started = {n: p.start() for n, p in patches.items()}
        started["repo"] = started["repo"].return_value
        try:
            started["get_settings"].return_value = settings
            started["confirm"].return_value = False
            from media_dl.main import app

            CliRunner().invoke(app, ["playlist", playlist_info.url])
            assert started["download"].call_count == 0
        finally:
            for p in patches.values():
                p.stop()


class TestHistory:
    def test_records_video_quality(self, playlist_info, settings, tmp_path):
        target = tmp_path / "salida"
        target.mkdir()
        real = target / "v.mp4"
        real.write_bytes(b"z" * 100)

        _, mocks = run_playlist(
            ["playlist", playlist_info.url, "--range", "1"],
            playlist_info,
            settings,
            download_result=str(real),
        )
        repo = mocks["repo"]
        assert repo.add.call_count == 1
        assert repo.add.call_args.kwargs["media_type"] == "video"

    def test_audio_uses_mp3_extension(self, playlist_info, settings, tmp_path):
        target = tmp_path / "salida"
        target.mkdir()
        real = target / "v.m4a"
        real.write_bytes(b"z" * 100)

        _, mocks = run_playlist(
            ["playlist", playlist_info.url, "--range", "1", "-t", "audio"],
            playlist_info,
            settings,
            download_result=str(real),
        )
        kwargs = mocks["repo"].add.call_args.kwargs
        assert kwargs["file_path"].endswith(".mp3")
        assert "192kbps" in kwargs["quality"]

    def test_skips_duplicates(self, playlist_info, settings):
        _, mocks = run_playlist(
            ["playlist", playlist_info.url],
            playlist_info,
            settings,
            is_duplicate=MagicMock(title="Ya estaba"),
        )
        mocks["download"].assert_not_called()
        mocks["repo"].add.assert_not_called()


class TestNotAPlaylist:
    def test_single_video_is_rejected(self, settings):
        video = MediaInfo(
            id="v1",
            title="Un video",
            url="https://youtube.com/watch?v=v1",
            platform="YouTube",
            is_playlist=False,
        )
        from media_dl.cli.commands.playlist import playlist

        with (
            patch("media_dl.cli.commands.playlist.get_settings", return_value=settings),
            patch("media_dl.cli.commands.playlist.get_extractor"),
            patch("media_dl.cli.commands.playlist._run_async", return_value=video),
            pytest.raises(typer.Exit),
        ):
            playlist(ctx=None, url=video.url)
