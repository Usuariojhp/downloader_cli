"""CLI commands package exports."""

from media_dl.cli.commands.config import app as config_app
from media_dl.cli.commands.doctor import app as doctor_app
from media_dl.cli.commands.download import app as download_app
from media_dl.cli.commands.history import app as history_app
from media_dl.cli.commands.playlist import playlist

__all__ = [
    "config_app",
    "doctor_app",
    "download_app",
    "history_app",
    "playlist",
]
