"""Tests for settings persistence and validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from media_dl.config import Settings, get_settings, reset_settings
from media_dl.config.settings import CONFIG_FILE_NAME, default_config_dir


def make_settings(tmp_path: Path, **overrides) -> Settings:
    values = {
        "download_path": tmp_path / "downloads",
        "config_dir": tmp_path / "config",
        "db_path": tmp_path / "config" / "history.db",
    }
    values.update(overrides)
    return Settings(**values)


class TestDefaults:
    def test_factory_defaults(self, tmp_path):
        settings = Settings.defaults(config_dir=tmp_path, db_path=tmp_path / "h.db")
        assert settings.download_mode == "ultra"
        assert settings.default_audio_bitrate == 192
        assert settings.aria2c_connections == 16
        assert settings.check_duplicates is True
        assert settings.concurrent_downloads == 3

    def test_defaults_ignore_json_file(self, tmp_path):
        """``Settings.defaults()`` must not pick values up from config.json."""
        stored = make_settings(tmp_path, retry_attempts=7)
        stored.save_config()

        fresh = Settings.defaults(config_dir=tmp_path, db_path=tmp_path / "h.db")
        assert fresh.retry_attempts == 3

    def test_default_config_dir_uses_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MEDIA_DL_CONFIG_DIR", str(tmp_path))
        assert default_config_dir() == tmp_path


class TestPersistence:
    def test_save_creates_file(self, tmp_path):
        settings = make_settings(tmp_path)
        path = settings.save_config()

        assert path == tmp_path / "config" / CONFIG_FILE_NAME
        assert path.is_file()

    def test_roundtrip(self, tmp_path):
        make_settings(tmp_path, retry_attempts=5, download_mode="normal").save_config()

        reloaded = make_settings(tmp_path)
        assert reloaded.retry_attempts == 5
        assert reloaded.download_mode == "normal"

    def test_runtime_paths_not_persisted(self, tmp_path):
        settings = make_settings(tmp_path)
        saved = settings.to_config_dict()

        assert "config_dir" not in saved
        assert "db_path" not in saved
        assert "download_path" in saved

    def test_init_kwargs_win_over_json(self, tmp_path):
        make_settings(tmp_path, retry_attempts=5).save_config()

        reloaded = make_settings(tmp_path, retry_attempts=2)
        assert reloaded.retry_attempts == 2

    def test_env_wins_over_json(self, tmp_path, monkeypatch):
        make_settings(tmp_path, retry_attempts=5).save_config()

        monkeypatch.setenv("MEDIA_DL_RETRY_ATTEMPTS", "4")
        reloaded = Settings(config_dir=tmp_path, db_path=tmp_path / "h.db")
        assert reloaded.retry_attempts == 4

    def test_corrupt_json_is_ignored(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)
        (config_dir / CONFIG_FILE_NAME).write_text("{no es json", encoding="utf-8")

        reloaded = make_settings(tmp_path)
        assert reloaded.retry_attempts == 3

    def test_unknown_keys_in_json_are_ignored(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)
        (config_dir / CONFIG_FILE_NAME).write_text(
            '{"retry_attempts": 6, "clave_fantasma": 1}', encoding="utf-8"
        )

        reloaded = make_settings(tmp_path)
        assert reloaded.retry_attempts == 6


class TestValidation:
    def test_assignment_is_validated(self, tmp_path):
        settings = make_settings(tmp_path)
        with pytest.raises(ValidationError):
            settings.default_audio_format = "bogus"

    def test_ranges_are_enforced(self, tmp_path):
        settings = make_settings(tmp_path)
        with pytest.raises(ValidationError):
            settings.aria2c_connections = 99
        with pytest.raises(ValidationError):
            settings.retry_attempts = 0

    def test_ensure_directories(self, tmp_path):
        settings = make_settings(tmp_path)
        settings.ensure_directories()

        assert settings.download_path.is_dir()
        assert settings.config_dir.is_dir()
        assert settings.db_path.parent.is_dir()


class TestSingleton:
    def test_get_settings_is_cached(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MEDIA_DL_CONFIG_DIR", str(tmp_path))
        reset_settings()

        first = get_settings()
        assert get_settings() is first

        reset_settings()
        assert get_settings() is not first


class TestSpotifyCredentials:
    def test_spotify_credentials_default_empty(self, tmp_path):
        settings = make_settings(tmp_path)
        assert settings.spotify_client_id == ""
        assert settings.spotify_client_secret == ""

    def test_spotify_credentials_roundtrip(self, tmp_path):
        settings = make_settings(
            tmp_path,
            spotify_client_id="test_client_id",
            spotify_client_secret="test_client_secret",
        )
        settings.save_config()

        reloaded = make_settings(tmp_path)
        assert reloaded.spotify_client_id == "test_client_id"
        assert reloaded.spotify_client_secret == "test_client_secret"

    def test_spotify_credentials_env_override(self, tmp_path, monkeypatch):
        make_settings(tmp_path, spotify_client_id="from_json").save_config()

        monkeypatch.setenv("MEDIA_DL_SPOTIFY_CLIENT_ID", "from_env")
        monkeypatch.setenv("MEDIA_DL_SPOTIFY_CLIENT_SECRET", "secret_from_env")

        reloaded = Settings(config_dir=tmp_path, db_path=tmp_path / "h.db")
        assert reloaded.spotify_client_id == "from_env"
        assert reloaded.spotify_client_secret == "secret_from_env"

    def test_spotify_credentials_in_config_dict(self, tmp_path):
        settings = make_settings(
            tmp_path,
            spotify_client_id="id123",
            spotify_client_secret="secret123",
        )
        saved = settings.to_config_dict()
        assert saved["spotify_client_id"] == "id123"
        assert saved["spotify_client_secret"] == "secret123"
