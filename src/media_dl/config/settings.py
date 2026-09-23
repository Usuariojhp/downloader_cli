"""Configuration settings using Pydantic Settings."""

from pathlib import Path
from typing import Literal, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import platformdirs


class Settings(BaseSettings):
    """Application settings with validation and persistence."""

    # Paths
    download_path: Path = Field(default_factory=lambda: Path("./downloads"))
    config_dir: Path = Field(
        default_factory=lambda: Path(platformdirs.user_config_dir("media-dl"))
    )
    db_path: Path = Field(default_factory=lambda: Path(platformdirs.user_config_dir("media-dl")) / "history.db")

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
    subtitle_languages: List[str] = Field(default_factory=lambda: ["es", "en"])

    # Retry and duplicate handling
    retry_attempts: int = Field(default=3, ge=1, le=10)
    check_duplicates: bool = True
    concurrent_downloads: int = Field(default=3, ge=1, le=8)

    # Post-processing
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    write_info_json: bool = False

    model_config = SettingsConfigDict(
        env_prefix="MEDIA_DL_",
        json_file="config.json",
        json_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("download_path", "config_dir", "db_path", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        if isinstance(v, str):
            v = Path(v)
        return v.expanduser().resolve()

    def ensure_directories(self) -> None:
        """Create necessary directories."""
        self.download_path.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)


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