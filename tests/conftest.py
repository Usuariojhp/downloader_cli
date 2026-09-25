"""Test configuration and fixtures."""

import os
import tempfile
from pathlib import Path

import pytest

from media_dl.config import Settings, reset_settings
from media_dl.core.history import HistoryRepository
from media_dl.core.models import Format, MediaInfo, PlaylistEntry


@pytest.fixture(autouse=True, scope="session")
def isolated_config_dir(tmp_path_factory):
    """Point MEDIA_DL_CONFIG_DIR to a temp dir so tests never touch user config/DB."""
    config_dir = tmp_path_factory.mktemp("media-dl-config")
    previous = os.environ.get("MEDIA_DL_CONFIG_DIR")
    os.environ["MEDIA_DL_CONFIG_DIR"] = str(config_dir)
    yield config_dir
    if previous is None:
        os.environ.pop("MEDIA_DL_CONFIG_DIR", None)
    else:
        os.environ["MEDIA_DL_CONFIG_DIR"] = previous


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config singleton before each test."""
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def test_settings(temp_dir):
    """Create test settings with temp directories."""
    settings = Settings(
        download_path=temp_dir / "downloads",
        config_dir=temp_dir / "config",
        db_path=temp_dir / "config" / "test.db",
    )
    settings.ensure_directories()
    return settings


@pytest.fixture
def history_repo(test_settings):
    """Create test history repository."""
    return HistoryRepository(test_settings.db_path)


@pytest.fixture
def sample_media_info():
    """Create sample MediaInfo for testing."""
    return MediaInfo(
        id="test123",
        title="Test Video",
        url="https://youtube.com/watch?v=test123",
        platform="YouTube",
        uploader="Test Channel",
        duration=300,
        thumbnail="https://example.com/thumb.jpg",
        formats=[
            Format(
                format_id="137",
                ext="mp4",
                resolution="1080p",
                height=1080,
                vcodec="avc1",
                acodec="mp4a",
                filesize=50000000,
                tbr=5000,
                quality_note="1080p",
            ),
            Format(
                format_id="140",
                ext="m4a",
                vcodec="none",
                acodec="mp4a",
                filesize=5000000,
                abr=128,
                quality_note="128kbps",
            ),
        ],
        is_playlist=False,
    )


@pytest.fixture
def sample_playlist_info():
    """Create sample playlist MediaInfo."""
    return MediaInfo(
        id="PLtest123",
        title="Test Playlist",
        url="https://youtube.com/playlist?list=PLtest123",
        platform="YouTube",
        uploader="Test Channel",
        is_playlist=True,
        playlist_title="Test Playlist",
        playlist_id="PLtest123",
        playlist_count=3,
        entries=[
            PlaylistEntry(
                id="vid1",
                title="Video 1",
                url="https://youtube.com/watch?v=vid1",
                duration=100,
                index=1,
            ),
            PlaylistEntry(
                id="vid2",
                title="Video 2",
                url="https://youtube.com/watch?v=vid2",
                duration=200,
                index=2,
            ),
            PlaylistEntry(
                id="vid3",
                title="Video 3",
                url="https://youtube.com/watch?v=vid3",
                duration=300,
                index=3,
            ),
        ],
    )


@pytest.fixture
def sample_format():
    """Create sample Format."""
    return Format(
        format_id="137",
        ext="mp4",
        resolution="1080p",
        height=1080,
        vcodec="avc1",
        acodec="mp4a",
        filesize=50000000,
        tbr=5000,
        quality_note="1080p",
    )
