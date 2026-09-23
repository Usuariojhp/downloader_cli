"""CLI commands package exports."""

from media_dl.cli.commands.download import app as download_app
from media_dl.cli.commands.playlist import app as playlist_app
from media_dl.cli.commands.history import app as history_app
from media_dl.cli.commands.config import app as config_app
from media_dl.cli.commands.doctor import app as doctor_app

__all__ = [
    "download_app",
    "playlist_app",
    "history_app",
    "config_app",
    "doctor_app",
]