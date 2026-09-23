"""CLI package exports."""

from media_dl.cli.commands import (
    download_app,
    playlist_app,
    history_app,
    config_app,
    doctor_app,
)

__all__ = [
    "download_app",
    "playlist_app",
    "history_app",
    "config_app",
    "doctor_app",
]