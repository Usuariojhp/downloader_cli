"""CLI commands package exports."""

from veluz.cli.commands.config import app as config_app
from veluz.cli.commands.doctor import app as doctor_app
from veluz.cli.commands.download import app as download_app
from veluz.cli.commands.history import app as history_app
from veluz.cli.commands.playlist import playlist

__all__ = [
    "config_app",
    "doctor_app",
    "download_app",
    "history_app",
    "playlist",
]
