"""History models using raw SQLite (no SQLAlchemy)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class DownloadHistory:
    """Download history record."""

    id: int | None = None
    url: str = ""
    url_hash: str = ""
    title: str = ""
    platform: str = ""
    media_type: str = ""
    quality: str = ""
    file_path: str = ""
    file_size: int = 0
    file_hash: str | None = None
    download_date: datetime | None = None
    status: str = "completed"
    info_json: dict[str, Any] | None = None
    duration: int | None = None
    uploader: str | None = None
    thumbnail: str | None = None


@dataclass
class SettingsHistory:
    """Settings change history."""

    id: int | None = None
    key: str = ""
    old_value: str | None = None
    new_value: str | None = None
    changed_at: datetime | None = None
