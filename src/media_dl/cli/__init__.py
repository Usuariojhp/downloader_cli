"""CLI package exports."""

from media_dl.cli.commands import (
    config_app,
    doctor_app,
    download_app,
    history_app,
    playlist,
)

__all__ = [
    "config_app",
    "doctor_app",
    "download_app",
    "history_app",
    "playlist",
]
