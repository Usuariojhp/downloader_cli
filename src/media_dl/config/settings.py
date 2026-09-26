"""Configuration settings using Pydantic Settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

import platformdirs
from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

CONFIG_DIR_ENV = "MEDIA_DL_CONFIG_DIR"
CONFIG_FILE_NAME = "config.json"
RUNTIME_FIELDS = {"config_dir", "db_path"}


def default_config_dir() -> Path:
    """Return the default configuration directory."""
    return Path(os.environ.get(CONFIG_DIR_ENV) or platformdirs.user_config_dir("media-dl"))


def default_config_file() -> Path:
    """Return the path of the JSON configuration file."""
    return default_config_dir() / CONFIG_FILE_NAME


class _ConfigFileSource(PydanticBaseSettingsSource):
    """Read user preferences from ``<config_dir>/config.json``.

    The path is resolved lazily (on call) so that ``config_dir`` coming from init
    kwargs or environment variables is already known at that point.
    """

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        resolved = self.current_state.get("config_dir")
        base = Path(resolved) if resolved else default_config_dir()
        path = base / CONFIG_FILE_NAME

        if not path.is_file():
            return {}

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        if not isinstance(data, dict):
            return {}

        known = self.settings_cls.model_fields
        return {key: value for key, value in data.items() if key in known}


class Settings(BaseSettings):
    """Application settings with validation and persistence."""

    # Paths
    download_path: Path = Field(default_factory=lambda: Path("./downloads"))
    config_dir: Path = Field(default_factory=default_config_dir)
    db_path: Path = Field(default_factory=lambda: default_config_dir() / "history.db")

    # Download behavior
    download_mode: Literal["ultra", "normal"] = "ultra"
    default_video_quality: str = "auto"
    default_audio_format: Literal["original", "mp3"] = "mp3"
    default_audio_bitrate: Literal[128, 192, 320] = 192

    # Aria2c settings
    aria2c_connections: int = Field(default=16, ge=4, le=32)
    aria2c_split: int = Field(default=16, ge=1, le=32)
    max_download_speed: int = Field(default=0, ge=0)

    # Subtitles
    auto_subtitle: bool = False
    subtitle_languages: list[str] = Field(default_factory=lambda: ["es", "en"])

    # Retry and duplicate handling
    retry_attempts: int = Field(default=3, ge=1, le=10)
    check_duplicates: bool = True
    concurrent_downloads: int = Field(default=3, ge=1, le=8)

    # Post-processing
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    write_info_json: bool = False

    # Spotify API credentials (optional, for higher rate limits)
    spotify_client_id: str = Field(default="", description="Spotify API Client ID")
    spotify_client_secret: str = Field(default="", description="Spotify API Client Secret")

    model_config = SettingsConfigDict(
        env_prefix="MEDIA_DL_",
        extra="ignore",
        validate_assignment=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Precedence: init kwargs > env > config.json > secrets."""
        return (
            init_settings,
            env_settings,
            _ConfigFileSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

    @field_validator("download_path", "config_dir", "db_path", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        if isinstance(v, str):
            v = Path(v)
        return v.expanduser().resolve()

    @property
    def config_file(self) -> Path:
        """Path of the JSON configuration file."""
        return self.config_dir / CONFIG_FILE_NAME

    def ensure_directories(self) -> None:
        """Create necessary directories."""
        self.download_path.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def to_config_dict(self) -> dict[str, Any]:
        """Serializable user preferences (runtime paths excluded)."""
        return self.model_dump(mode="json", exclude=RUNTIME_FIELDS)

    @classmethod
    def defaults(cls, **overrides: Any) -> Settings:
        """Build settings from factory defaults, ignoring the JSON config file."""
        values: dict[str, Any] = {
            name: field.get_default(call_default_factory=True)
            for name, field in cls.model_fields.items()
        }
        values.update(overrides)
        return cls(**values)

    def save_config(self) -> Path:
        """Persist user preferences to the JSON configuration file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        path = self.config_file
        payload = json.dumps(self.to_config_dict(), indent=2, ensure_ascii=False)
        path.write_text(payload + "\n", encoding="utf-8")
        return path


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Get singleton settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
        _settings_instance.ensure_directories()
    return _settings_instance


def reset_settings() -> None:
    """Reset singleton for testing."""
    global _settings_instance
    _settings_instance = None
