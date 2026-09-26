"""Tests for CLI commands."""

import importlib
import re
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from media_dl.config import Settings
from media_dl.core.models import Format, MediaInfo
from media_dl.main import app

runner = CliRunner()


def make_settings(tmp_path, **overrides):
    """Settings isolated in a temp dir so tests never touch the user config."""
    values = {
        "download_path": tmp_path / "downloads",
        "config_dir": tmp_path / "config",
        "db_path": tmp_path / "config" / "test.db",
        "download_mode": "normal",
        "retry_attempts": 1,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def mock_settings(tmp_path):
    with patch("media_dl.cli.commands.download.get_settings") as mock:
        mock.return_value = make_settings(tmp_path)
        yield mock.return_value


@pytest.fixture
def mock_extractor():
    with patch("media_dl.cli.commands.download.get_extractor") as mock:
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
    with patch("media_dl.cli.commands.download.HistoryRepository") as mock:
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
            Format(
                format_id="137",
                ext="mp4",
                height=1080,
                vcodec="avc1",
                acodec="mp4a",
                filesize=50000000,
            ),
            Format(
                format_id="140", ext="m4a", vcodec="none", acodec="mp4a", filesize=5000000, abr=128
            ),
        ],
    )


class TestDownloadVideo:
    def test_download_video_success(
        self,
        mock_settings,
        mock_extractor,
        mock_strategy,
        mock_history_repo,
        sample_media_info,
        tmp_path,
    ):
        mock_extractor.extract.return_value = sample_media_info

        with patch("media_dl.cli.commands.download._run_async") as mock_run:
            mock_run.return_value = sample_media_info

            destino = tmp_path / "test_video.mp4"
            destino.write_bytes(b"x" * 50_000_000)

            with patch("media_dl.cli.commands.download._download_with_retry") as mock_download:
                mock_download.return_value = str(destino)

                result = runner.invoke(
                    app, ["download", "video", "https://youtube.com/watch?v=test123"]
                )

                assert result.exit_code == 0
                assert "Descarga Completada" in result.stdout or "Video guardado" in result.stdout

    def test_download_video_invalid_url(self):
        result = runner.invoke(app, ["download", "video", "not-a-url"])
        assert result.exit_code != 0
        assert "URL" in result.stdout or "Error" in result.stdout


class TestDownloadAudio:
    def test_download_audio_success(
        self,
        mock_settings,
        mock_extractor,
        mock_strategy,
        mock_history_repo,
        sample_media_info,
        tmp_path,
    ):
        mock_extractor.extract.return_value = sample_media_info

        with patch("media_dl.cli.commands.download._run_async") as mock_run:
            mock_run.return_value = sample_media_info

            m4a = tmp_path / "test_audio.m4a"
            m4a.write_bytes(b"y" * 5_000_000)
            mp3 = tmp_path / "test_audio.mp3"
            mp3.write_bytes(b"y" * 5_000_000)

            with patch("media_dl.cli.commands.download._download_with_retry") as mock_download:
                mock_download.return_value = str(m4a)

                result = runner.invoke(
                    app, ["download", "audio", "https://youtube.com/watch?v=test123"]
                )

                assert result.exit_code == 0


@pytest.fixture
def mock_history_repo_cmd():
    with patch("media_dl.cli.commands.history.HistoryRepository") as mock:
        repo = MagicMock()
        repo.list.return_value = []
        repo.count.return_value = 0
        mock.return_value = repo
        yield repo


@pytest.fixture
def mock_settings_cmd(tmp_path):
    with patch("media_dl.cli.commands.config.get_settings") as mock:
        mock.return_value = make_settings(tmp_path)
        yield mock.return_value


class TestHistory:
    def test_history_command(self, mock_history_repo_cmd):
        result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
        assert "Historial Vacío" in result.stdout or "historial" in result.stdout.lower()

    def test_history_stats(self, mock_history_repo_cmd):
        mock_history_repo_cmd.get_stats.return_value = {
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
    def test_config_show(self, mock_settings_cmd):
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "CONFIGURACIÓN" in result.stdout or "config" in result.stdout.lower()

    def test_config_path(self, mock_settings_cmd):
        result = runner.invoke(app, ["config", "path"])
        assert result.exit_code == 0
        assert "RUTAS" in result.stdout or "path" in result.stdout.lower()

    def test_config_set_persists(self, mock_settings_cmd):
        result = runner.invoke(app, ["config", "set", "retry_attempts", "5"])
        assert result.exit_code == 0
        assert mock_settings_cmd.retry_attempts == 5

    def test_config_set_rejects_out_of_range(self, mock_settings_cmd):
        result = runner.invoke(app, ["config", "set", "retry_attempts", "99"])
        assert result.exit_code == 1
        assert mock_settings_cmd.retry_attempts == 1

    def test_config_set_rejects_unknown_key(self, mock_settings_cmd):
        result = runner.invoke(app, ["config", "set", "nope", "1"])
        assert result.exit_code == 1

    def test_config_set_spotify_secret_masks_value(self, mock_settings_cmd):
        """Secret values should be masked in output, not logged in plaintext."""
        result = runner.invoke(app, ["config", "set", "spotify_client_secret", "my_secret"])
        assert result.exit_code == 0
        assert "my_secret" not in result.stdout
        assert "***" in result.stdout
        assert mock_settings_cmd.spotify_client_secret == "my_secret"


def _plano(texto: str) -> str:
    """Deja el texto en una linea, quitando bordes de tabla y espacios.

    Rich parte los textos largos en varias lineas y mete los bordes de la
    tabla entre los trozos, asi que sin limpiar no se puede comprobar si
    una frase aparece.
    """
    limpio = re.sub(r"[\u2502-\u257f\s]+", " ", texto)
    return re.sub(r"\s+", " ", limpio).strip()


class TestDoctor:
    def test_doctor_command(self):
        with (
            patch("shutil.which", return_value="/usr/bin/aria2c"),
            patch("importlib.import_module") as mock_import,
        ):
            mock_import.return_value.__version__ = "2024.1.0"

            result = runner.invoke(app, ["doctor"])
            assert result.exit_code == 0
            assert "DIAGNÓSTICO" in result.stdout or "diagnostico" in result.stdout.lower()

    def test_broken_extra_is_not_reported_as_all_ready(self):
        """Sin spotdl no se puede descargar de Spotify, y hay que decirlo.

        Celebrar un "Sistema Listo" con Spotify roto lleva al usuario a
        pensar que el binario va bien cuando no va: fue exactamente lo que
        pasó con el spec, que dejaba websockets fuera y rompia 'import
        spotdl' sin que nada lo delatara salvo esta tabla.
        """
        real_import = importlib.import_module

        def solo_sin_spotdl(nombre, *args, **kwargs):
            if nombre == "spotdl":
                raise ImportError("No instalado")
            return real_import(nombre, *args, **kwargs)

        with (
            patch("shutil.which", return_value="/usr/bin/aria2c"),
            patch("importlib.import_module", side_effect=solo_sin_spotdl),
        ):
            result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0
        assert "NO funcionan" in _plano(result.stdout)
        assert "spotdl (Spotify)" in _plano(result.stdout)

    def test_healthy_system_says_ready(self):
        with (
            patch("shutil.which", return_value="/usr/bin/aria2c"),
            patch("importlib.import_module") as mock_import,
        ):
            mock_import.return_value.__version__ = "2024.1.0"
            result = runner.invoke(app, ["doctor"])

        assert "Sistema Listo" in _plano(result.stdout)
        assert "NO funcionan" not in _plano(result.stdout)

    def test_frozen_binary_does_not_advise_pip(self):
        """En el binario portable no se puede hacer pip install: no lo digas."""
        real_import = importlib.import_module

        def solo_sin_spotdl(nombre, *args, **kwargs):
            if nombre == "spotdl":
                raise ImportError("No instalado")
            return real_import(nombre, *args, **kwargs)

        with (
            patch("shutil.which", return_value="/usr/bin/aria2c"),
            patch("importlib.import_module", side_effect=solo_sin_spotdl),
            patch.object(sys, "frozen", True, create=True),
        ):
            result = runner.invoke(app, ["doctor"])

        assert "no incluido en este binario" in _plano(result.stdout)
        assert "pip install" not in _plano(result.stdout)

    def test_strict_falla_si_no_hay_mutagen(self):
        """Sin mutagen no hay carátula, y no se nota hasta que se descarga.

        cover.embed_cover se traga cualquier excepción y devuelve False, así
        que si mutagen se pierde del binario las descargas salen sin portada y
        sin decir nada. Pasó de verdad: al cambiar el import de mutagen a uno
        dinámico para callar a mypy, PyInstaller dejó de empaquetarlo.
        """
        real_import = importlib.import_module

        def solo_sin_mutagen(nombre, *args, **kwargs):
            if nombre.startswith("mutagen"):
                raise ImportError("No instalado")
            return real_import(nombre, *args, **kwargs)

        with (
            patch("shutil.which", return_value="/usr/bin/aria2c"),
            patch("importlib.import_module", side_effect=solo_sin_mutagen),
        ):
            result = runner.invoke(app, ["doctor", "--strict"])

        assert result.exit_code == 1
        assert "Carátulas incrustadas" in _plano(result.stdout)

    def test_strict_falla_si_falta_una_extension(self):
        """Este es el guard que atrapa al spec: sin el, el build pasa en verde.

        Antes el workflow solo comprobaba que la cadena 'doctor --strict'
        estuviera en el YAML, sin ejecutar nada, asi que un spec que dejaba
        spotdl fuera no rompia la CI.
        """
        real_import = importlib.import_module

        def solo_sin_spotdl(nombre, *args, **kwargs):
            if nombre == "spotdl":
                raise ImportError("No instalado")
            return real_import(nombre, *args, **kwargs)

        with (
            patch("shutil.which", return_value="/usr/bin/aria2c"),
            patch("importlib.import_module", side_effect=solo_sin_spotdl),
        ):
            result = runner.invoke(app, ["doctor", "--strict"])

        assert result.exit_code == 1

    def test_strict_no_falla_por_faltar_ffmpeg(self):
        """ffmpeg y aria2c no se empaquetan: su ausencia avisa, pero no rompe.

        El binario no puede llevar programas del sistema dentro. Si --strict
        los contara, cualquier runner de CI sin ffmpeg (que es el caso normal)
        dejaria el build en rojo por algo que no es un defecto del artefacto.
        scdl se deja en su sitio porque si se empaqueta con el binario.
        """

        def solo_sin_externas(nombre, *args, **kwargs):
            return None if nombre in {"aria2c", "ffmpeg"} else f"/usr/bin/{nombre}"

        with (
            patch("shutil.which", side_effect=solo_sin_externas),
            patch("importlib.import_module") as mock_import,
        ):
            mock_import.return_value.__version__ = "2024.1.0"
            result = runner.invoke(app, ["doctor", "--strict"])

        assert result.exit_code == 0
        # aun asi avisa de que conversion no estara disponible
        assert "ffmpeg" in _plano(result.stdout)


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
        assert parse_range("TODO", 10) is None
        assert parse_range("*", 10) is None
        assert parse_range("", 10) == []

        # Invalid range
        with pytest.raises(ValueError, match="Formato de rango inválido"):
            parse_range("5-3", 10)  # start > end

        with pytest.raises(ValueError, match="Índice inválido"):
            parse_range("11", 10)  # out of bounds

        with pytest.raises(ValueError, match="Índice inválido"):
            parse_range("abc", 10)

        with pytest.raises(ValueError, match="Formato de rango inválido"):
            parse_range("1-x", 10)

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
