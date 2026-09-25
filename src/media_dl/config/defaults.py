"""Default configuration values."""

from pathlib import Path

import platformdirs

DEFAULT_DOWNLOAD_PATH = Path("./downloads")
DEFAULT_CONFIG_DIR = Path(platformdirs.user_config_dir("media-dl"))
DEFAULT_DB_PATH = DEFAULT_CONFIG_DIR / "history.db"

DEFAULT_SETTINGS = {
    "download_path": str(DEFAULT_DOWNLOAD_PATH),
    "download_mode": "ultra",
    "default_video_quality": "auto",
    "default_audio_format": "mp3",
    "default_audio_bitrate": 192,
    "aria2c_connections": 16,
    "aria2c_split": 16,
    "max_download_speed": 0,
    "auto_subtitle": False,
    "subtitle_languages": ["es", "en"],
    "retry_attempts": 3,
    "check_duplicates": True,
    "concurrent_downloads": 3,
    "embed_thumbnail": True,
    "embed_metadata": True,
    "write_info_json": False,
}
