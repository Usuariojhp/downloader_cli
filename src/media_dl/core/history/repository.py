"""Repository for download history operations using raw SQLite."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator
import hashlib
import json
import sqlite3
from sqlite3 import Connection

from media_dl.core.history.models import DownloadHistory, SettingsHistory
from media_dl.core.exceptions import HistoryError
from media_dl.config import get_settings


class HistoryRepository:
    """Repository for managing download history with raw SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        settings = get_settings()
        self.db_path = db_path or settings.db_path
        self._init_db()

    def _get_connection(self) -> Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    url_hash TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    quality TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_hash TEXT,
                    download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'completed',
                    info_json TEXT,
                    duration INTEGER,
                    uploader TEXT,
                    thumbnail TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_downloads_url_hash ON downloads(url_hash);
                CREATE INDEX IF NOT EXISTS idx_downloads_platform ON downloads(platform);
                CREATE INDEX IF NOT EXISTS idx_downloads_media_type ON downloads(media_type);
                CREATE INDEX IF NOT EXISTS idx_downloads_date ON downloads(download_date);
                CREATE INDEX IF NOT EXISTS idx_downloads_file_hash ON downloads(file_hash);

                CREATE TABLE IF NOT EXISTS settings_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

    @contextmanager
    def _transaction(self) -> Generator[Connection, None, None]:
        """Transaction context manager."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _compute_url_hash(url: str) -> str:
        """Compute SHA256 hash of URL."""
        return hashlib.sha256(url.encode()).hexdigest()

    @staticmethod
    def _compute_file_hash(filepath: Path) -> Optional[str]:
        """Compute SHA256 hash of file (first 1MB for speed)."""
        try:
            if not filepath.exists():
                return None
            hasher = hashlib.sha256()
            with open(filepath, "rb") as f:
                chunk = f.read(1024 * 1024)
                hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    def _row_to_history(self, row: sqlite3.Row) -> DownloadHistory:
        """Convert database row to DownloadHistory."""
        info_json = None
        if row["info_json"]:
            try:
                info_json = json.loads(row["info_json"])
            except json.JSONDecodeError:
                pass

        download_date = None
        if row["download_date"]:
            try:
                download_date = datetime.fromisoformat(row["download_date"])
            except ValueError:
                pass

        changed_at = None
        # Not used for DownloadHistory

        return DownloadHistory(
            id=row["id"],
            url=row["url"],
            url_hash=row["url_hash"],
            title=row["title"],
            platform=row["platform"],
            media_type=row["media_type"],
            quality=row["quality"],
            file_path=row["file_path"],
            file_size=row["file_size"],
            file_hash=row["file_hash"],
            download_date=download_date,
            status=row["status"],
            info_json=info_json,
            duration=row["duration"],
            uploader=row["uploader"],
            thumbnail=row["thumbnail"],
        )

    def _row_to_settings_history(self, row: sqlite3.Row) -> SettingsHistory:
        """Convert database row to SettingsHistory."""
        changed_at = None
        if row["changed_at"]:
            try:
                changed_at = datetime.fromisoformat(row["changed_at"])
            except ValueError:
                pass

        return SettingsHistory(
            id=row["id"],
            key=row["key"],
            old_value=row["old_value"],
            new_value=row["new_value"],
            changed_at=changed_at,
        )

    def add(
        self,
        url: str,
        title: str,
        platform: str,
        media_type: str,
        quality: str,
        file_path: str,
        file_size: int,
        status: str = "completed",
        duration: Optional[int] = None,
        uploader: Optional[str] = None,
        thumbnail: Optional[str] = None,
        info_json: Optional[Dict[str, Any]] = None,
    ) -> DownloadHistory:
        """Add a download record."""
        url_hash = self._compute_url_hash(url)
        file_hash = self._compute_file_hash(Path(file_path)) if file_path else None
        info_json_str = json.dumps(info_json) if info_json else None

        with self._transaction() as conn:
            # Check for existing URL hash
            existing = conn.execute(
                "SELECT * FROM downloads WHERE url_hash = ?", (url_hash,)
            ).fetchone()

            if existing:
                # Update existing record
                conn.execute("""
                    UPDATE downloads SET
                        title = ?, platform = ?, media_type = ?, quality = ?,
                        file_path = ?, file_size = ?, file_hash = ?, status = ?,
                        duration = ?, uploader = ?, thumbnail = ?,
                        info_json = ?, download_date = CURRENT_TIMESTAMP
                    WHERE url_hash = ?
                """, (title, platform, media_type, quality, file_path, file_size,
                      file_hash, status, duration, uploader, thumbnail,
                      info_json_str, url_hash))

                # Return updated record
                row = conn.execute(
                    "SELECT * FROM downloads WHERE url_hash = ?", (url_hash,)
                ).fetchone()
                return self._row_to_history(row)

            # Insert new record
            cursor = conn.execute("""
                INSERT INTO downloads (
                    url, url_hash, title, platform, media_type, quality,
                    file_path, file_size, file_hash, status, duration,
                    uploader, thumbnail, info_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (url, url_hash, title, platform, media_type, quality,
                  file_path, file_size, file_hash, status, duration,
                  uploader, thumbnail, info_json_str))

            record_id = cursor.lastrowid

            row = conn.execute(
                "SELECT * FROM downloads WHERE id = ?", (record_id,)
            ).fetchone()
            return self._row_to_history(row)

    def get_by_url_hash(self, url_hash: str) -> Optional[DownloadHistory]:
        """Get record by URL hash."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM downloads WHERE url_hash = ?", (url_hash,)
            ).fetchone()
            return self._row_to_history(row) if row else None

    def get_by_file_hash(self, file_hash: str) -> Optional[DownloadHistory]:
        """Get record by file hash."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM downloads WHERE file_hash = ?", (file_hash,)
            ).fetchone()
            return self._row_to_history(row) if row else None

    def is_duplicate(self, url: str, file_path: Optional[str] = None) -> Optional[DownloadHistory]:
        """Check if URL or file is a duplicate."""
        url_hash = self._compute_url_hash(url)

        with self._get_connection() as conn:
            # Check URL hash
            existing = conn.execute(
                "SELECT * FROM downloads WHERE url_hash = ?", (url_hash,)
            ).fetchone()

            if existing:
                return self._row_to_history(existing)

            # Check file hash if provided
            if file_path:
                file_hash = self._compute_file_hash(Path(file_path))
                if file_hash:
                    existing = conn.execute(
                        "SELECT * FROM downloads WHERE file_hash = ?", (file_hash,)
                    ).fetchone()
                    if existing:
                        return self._row_to_history(existing)

        return None

    def list(
        self,
        limit: int = 20,
        offset: int = 0,
        platform: Optional[str] = None,
        media_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[DownloadHistory]:
        """List download history with filters."""
        with self._get_connection() as conn:
            query = "SELECT * FROM downloads"
            params = []
            conditions = []

            if platform:
                conditions.append("platform = ?")
                params.append(platform)
            if media_type:
                conditions.append("media_type = ?")
                params.append(media_type)
            if status:
                conditions.append("status = ?")
                params.append(status)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY download_date DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_history(row) for row in rows]

    def count(
        self,
        platform: Optional[str] = None,
        media_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """Count total records with filters."""
        with self._get_connection() as conn:
            query = "SELECT COUNT(*) FROM downloads"
            params = []
            conditions = []

            if platform:
                conditions.append("platform = ?")
                params.append(platform)
            if media_type:
                conditions.append("media_type = ?")
                params.append(media_type)
            if status:
                conditions.append("status = ?")
                params.append(status)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            return conn.execute(query, params).fetchone()[0]

    def clear(self, platform: Optional[str] = None, media_type: Optional[str] = None) -> int:
        """Clear history records."""
        with self._transaction() as conn:
            query = "DELETE FROM downloads"
            params = []
            conditions = []

            if platform:
                conditions.append("platform = ?")
                params.append(platform)
            if media_type:
                conditions.append("media_type = ?")
                params.append(media_type)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            cursor = conn.execute(query, params)
            return cursor.rowcount

    def get_stats(self) -> Dict[str, Any]:
        """Get download statistics."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM downloads").fetchone()[0]
            total_size = conn.execute("SELECT SUM(file_size) FROM downloads").fetchone()[0] or 0

            by_platform = {}
            for row in conn.execute(
                "SELECT platform, COUNT(*) FROM downloads GROUP BY platform"
            ).fetchall():
                by_platform[row[0]] = row[1]

            by_type = {}
            for row in conn.execute(
                "SELECT media_type, COUNT(*) FROM downloads GROUP BY media_type"
            ).fetchall():
                by_type[row[0]] = row[1]

            recent_rows = conn.execute(
                "SELECT * FROM downloads ORDER BY download_date DESC LIMIT 5"
            ).fetchall()
            recent = [self._row_to_history(row) for row in recent_rows]

            return {
                "total_downloads": total,
                "total_size_bytes": total_size,
                "by_platform": by_platform,
                "by_type": by_type,
                "recent": recent,
            }

    def log_settings_change(self, key: str, old_value: Optional[str], new_value: Optional[str]) -> None:
        """Log a settings change."""
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO settings_history (key, old_value, new_value) VALUES (?, ?, ?)",
                (key, old_value, new_value),
            )

    def get_settings_history(self, limit: int = 50) -> List[SettingsHistory]:
        """Get settings change history."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM settings_history ORDER BY changed_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [self._row_to_settings_history(row) for row in rows]

    def vacuum(self) -> None:
        """Vacuum database to reclaim space."""
        with self._get_connection() as conn:
            conn.execute("VACUUM")