"""History models using raw SQLite (no SQLAlchemy)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
import json


@dataclass
class DownloadHistory:
    """Download history record."""
    id: Optional[int] = None
    url: str = ""
    url_hash: str = ""
    title: str = ""
    platform: str = ""
    media_type: str = ""
    quality: str = ""
    file_path: str = ""
    file_size: int = 0
    file_hash: Optional[str] = None
    download_date: Optional[datetime] = None
    status: str = "completed"
    info_json: Optional[Dict[str, Any]] = None
    duration: Optional[int] = None
    uploader: Optional[str] = None
    thumbnail: Optional[str] = None


@dataclass
class SettingsHistory:
    """Settings change history."""
    id: Optional[int] = None
    key: str = ""
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_at: Optional[datetime] = None