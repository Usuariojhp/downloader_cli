"""Tests for CLI commands."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from typer.testing import CliRunner

from media_dl.main import app
from media_dl.config import Settings
from media_dl.core.models import MediaInfo, Format, PlaylistEntry


runner = CliRunner()


@pytest.fixture
def mock_settings():
    with patch("media_dl.config.get_settings") as mock:
        settings = Settings(
            download_path="/tmp/downloads",
            download_mode="normal",
            retry_attempts=1,
        )
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_extractor():
    with patch("media_dl.core.extractors.get_extractor") as mock:
        extractor = MagicMock()
        extractor.extract = AsyncMock()
        mock.return_value = extractor
        yield extractor


@pytest.fixture
def mock_strategy():
    with patch("media_dl.core.strategies.StrategyFactory.get") as mock:
        strategy = MagicMock()
        strategy.name = "native"
        strategy.is_available.return_value = True
        strategy.build_args.return_value = {}
        mock.return_value = strategy
        yield strategy


@pytest.fixture
def mock_history_repo():
    with patch("media_dl.core.history.HistoryRepository") as mock:
        repo = MagicMock()
        repo.is_duplicate.return_value = None
        mock.return_value = repo
        yield repo


@pytest.fixture
def sample_media_info():
    return MediaInfo(
        id="test123",
        title="Test Video",
        url="https://youtube.com/watch?v=test123",
        platform="YouTube",
        uploader="Test Channel",
        duration=300,
        formats=[
            Format(format_id="137", ext="mp4", height=1080, vcodec="avc1", acodec="mp4a", filesize=50000000),
            Format(format_id="140", ext="m4a", vcodec="none", acodec="mp4a", filesize=5000000, abr=128),
        ],
    )


class TestDownloadVideo:
    def test_download_video_success(
        self, mock_settings, mock_extractor, mock_strategy, mock_history_repo, sample_media_info, tmp_path
    ):
        mock_extractor.extract.return_value = sample_media_info

        with patch("media_dl.cli.commands.download._run_async") as mock_run:
            mock_run.return_value = sample_media_info

            with patch("media_dl.cli.commands.download._download_with_retry") as mock_download:
                mock_download.return_value = str(tmp_path / "test_video.mp4")

                with patch("pathlib.Path.stat") as mock_stat:
                    mock_stat.return_value.st_size = 50000000

                    result = runner.invoke(app, ["download", "video", "https://youtube.com/watch?v=test123"])

                    assert result.exit_code == 0
                    assert "Descarga Completada" in result.stdout or "Video guardado" in result.stdout

    def test_download_video_invalid_url(self):
        result = runner.invoke(app, ["download", "video", "not-a-url"])
        assert result.exit_code != 0
        assert "URL" in result.stdout or "Error" in result.stdout


class TestDownloadAudio:
    def test_download_audio_success(
        self, mock_settings, mock_extractor, mock_strategy, mock_history_repo, sample_media_info, tmp_path
    ):
        mock_extractor.extract.return_value = sample_media_info

        with patch("media_dl.cli.commands.download._run_async") as mock_run:
            mock_run.return_value = sample_media_info

            with patch("media_dl.cli.commands.download._download_with_retry") as mock_download:
                mock_download.return_value = str(tmp_path / "test_audio.m4a")

                with patch("pathlib.Path.stat") as mock_stat:
                    mock_stat.return_value.st_size = 5000000

                    with patch("pathlib.Path.with_suffix") as mock_suffix:
                        mock_suffix.return_value = tmp_path / "test_audio.mp3"

                        result = runner.invoke(app, ["download", "audio", "https://youtube.com/watch?v=test123"])

                        assert result.exit_code == 0


class TestHistory:
    def test_history_command(self, mock_history_repo):
        mock_history_repo.list.return_value = []
        mock_history_repo.count.return_value = 0

        result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
        assert "Historial Vacío" in result.stdout or "historial" in result.stdout.lower()

    def test_history_stats(self, mock_history_repo):
        mock_history_repo.get_stats.return_value = {
            "total_downloads": 5,
            "total_size_bytes": 10000000,
            "by_platform": {"YouTube": 3, "TikTok": 2},
            "by_type": {"video": 4, "audio": 1},
            "recent": [],
        }

        result = runner.invoke(app, ["history", "--stats"])
        assert result.exit_code == 0
        assert "5" in result.stdout


class TestConfig:
    def test_config_show(self, mock_settings):
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "CONFIGURACIÓN" in result.stdout or "config" in result.stdout.lower()

    def test_config_path(self, mock_settings):
        result = runner.invoke(app, ["config", "path"])
        assert result.exit_code == 0
        assert "RUTAS" in result.stdout or "path" in result.stdout.lower()


class TestDoctor:
    def test_doctor_command(self):
        with patch("shutil.which", return_value="/usr/bin/aria2c"):
            with patch("importlib.import_module") as mock_import:
                mock_import.return_value.__version__ = "2024.1.0"

                result = runner.invoke(app, ["doctor"])
                assert result.exit_code == 0
                assert "DIAGNÓSTICO" in result.stdout or "diagnostico" in result.stdout.lower()


class TestMain:
    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "media-dl" in result.stdout

    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "media-dl" in result.stdout
        assert "download" in result.stdout
        assert "playlist" in result.stdout
        assert "history" in result.stdout
        assert "config" in result.stdout
        assert "doctor" in result.stdout

    def test_subcommand_help(self):
        result = runner.invoke(app, ["download", "--help"])
        assert result.exit_code == 0
        assert "video" in result.stdout
        assert "audio" in result.stdout
        assert "batch" in result.stdout


class TestPrompts:
    def test_parse_range(self):
        from media_dl.ui.prompts import parse_range

        # Simple range
        assert parse_range("1-5", 10) == [0, 1, 2, 3, 4]

        # Multiple ranges
        assert parse_range("1-2,5", 10) == [0, 1, 4]

        # Single items
        assert parse_range("1,3,5", 10) == [0, 2, 4]

        # All
        assert parse_range("all", 10) is None

        # Invalid range
        with pytest.raises(ValueError):
            parse_range("5-3", 10)  # start > end

        with pytest.raises(ValueError):
            parse_range("11", 10)  # out of bounds

    def test_format_size(self):
        from media_dl.ui.tables import format_size

        assert format_size(0) == "Desconocido"
        assert format_size(500) == "500.00 B"
        assert format_size(1024) == "1.00 KB"
        assert format_size(1024 * 1024) == "1.00 MB"
        assert format_size(1024 * 1024 * 1024) == "1.00 GB"

    def test_format_duration(self):
        from media_dl.ui.tables import format_duration

        assert format_duration(None) == "N/A"
        assert format_duration(30) == "0m 30s"
        assert format_duration(90) == "1m 30s"
        assert format_duration(3661) == "1h 1m 1s"