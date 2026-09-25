"""Tests for history repository."""

import hashlib

from media_dl.core.history import HistoryRepository


class TestHistoryRepository:
    def test_init_creates_tables(self, temp_dir):
        db_path = temp_dir / "test.db"
        HistoryRepository(db_path)
        assert db_path.exists()

    def test_add_and_get_by_url_hash(self, history_repo):
        record = history_repo.add(
            url="https://test.com/video1",
            title="Test Video",
            platform="YouTube",
            media_type="video",
            quality="1080p",
            file_path="/tmp/video.mp4",
            file_size=1000000,
        )

        assert record.id is not None
        assert record.url_hash == hashlib.sha256(b"https://test.com/video1").hexdigest()

        # Retrieve by hash
        found = history_repo.get_by_url_hash(record.url_hash)
        assert found is not None
        assert found.title == "Test Video"
        assert found.platform == "YouTube"

    def test_duplicate_url_updates_record(self, history_repo):
        # Add first
        history_repo.add(
            url="https://test.com/video1",
            title="Original Title",
            platform="YouTube",
            media_type="video",
            quality="720p",
            file_path="/tmp/video1.mp4",
            file_size=1000000,
        )

        # Add again with different title - should update
        record = history_repo.add(
            url="https://test.com/video1",
            title="Updated Title",
            platform="YouTube",
            media_type="video",
            quality="1080p",
            file_path="/tmp/video2.mp4",
            file_size=2000000,
        )

        # Should be same record (updated)
        found = history_repo.get_by_url_hash(record.url_hash)
        assert found.title == "Updated Title"
        assert found.quality == "1080p"
        assert found.file_size == 2000000

    def test_is_duplicate_by_url(self, history_repo):
        history_repo.add(
            url="https://test.com/video1",
            title="Test",
            platform="YouTube",
            media_type="video",
            quality="720p",
            file_path="/tmp/video.mp4",
            file_size=1000000,
        )

        duplicate = history_repo.is_duplicate("https://test.com/video1")
        assert duplicate is not None
        assert duplicate.title == "Test"

    def test_is_duplicate_by_file_hash(self, history_repo, temp_dir):
        # Create a test file
        test_file = temp_dir / "video.mp4"
        test_file.write_bytes(b"test content")

        history_repo.add(
            url="https://test.com/video1",
            title="Test",
            platform="YouTube",
            media_type="video",
            quality="720p",
            file_path=str(test_file),
            file_size=12,
        )

        # Check duplicate by file hash
        duplicate = history_repo.is_duplicate("https://test.com/other", file_path=str(test_file))
        assert duplicate is not None
        assert duplicate.title == "Test"

    def test_list_with_filters(self, history_repo):
        history_repo.add(
            url="https://youtube.com/v1",
            title="Video 1",
            platform="YouTube",
            media_type="video",
            quality="1080p",
            file_path="/tmp/v1.mp4",
            file_size=1000000,
        )
        history_repo.add(
            url="https://tiktok.com/v2",
            title="Video 2",
            platform="TikTok",
            media_type="video",
            quality="720p",
            file_path="/tmp/v2.mp4",
            file_size=500000,
        )
        history_repo.add(
            url="https://youtube.com/a1",
            title="Audio 1",
            platform="YouTube",
            media_type="audio",
            quality="mp3 192kbps",
            file_path="/tmp/a1.mp3",
            file_size=3000000,
        )

        # List all
        all_records = history_repo.list(limit=10)
        assert len(all_records) == 3

        # Filter by platform
        yt_records = history_repo.list(limit=10, platform="YouTube")
        assert len(yt_records) == 2

        # Filter by type
        audio_records = history_repo.list(limit=10, media_type="audio")
        assert len(audio_records) == 1

    def test_count(self, history_repo):
        history_repo.add(
            url="https://test.com/v1",
            title="V1",
            platform="YouTube",
            media_type="video",
            quality="1080p",
            file_path="/tmp/v1.mp4",
            file_size=1000,
        )
        history_repo.add(
            url="https://test.com/v2",
            title="V2",
            platform="YouTube",
            media_type="video",
            quality="720p",
            file_path="/tmp/v2.mp4",
            file_size=2000,
        )

        assert history_repo.count() == 2
        assert history_repo.count(platform="YouTube") == 2
        assert history_repo.count(media_type="audio") == 0

    def test_clear(self, history_repo):
        history_repo.add(
            url="https://test.com/v1",
            title="V1",
            platform="YouTube",
            media_type="video",
            quality="1080p",
            file_path="/tmp/v1.mp4",
            file_size=1000,
        )
        history_repo.add(
            url="https://test.com/v2",
            title="V2",
            platform="TikTok",
            media_type="video",
            quality="720p",
            file_path="/tmp/v2.mp4",
            file_size=2000,
        )

        # Clear all
        count = history_repo.clear()
        assert count == 2
        assert history_repo.count() == 0

        # Re-add
        history_repo.add(
            url="https://test.com/v3",
            title="V3",
            platform="YouTube",
            media_type="video",
            quality="1080p",
            file_path="/tmp/v3.mp4",
            file_size=1000,
        )

        # Clear only YouTube
        count = history_repo.clear(platform="YouTube")
        assert count == 1
        assert history_repo.count() == 0

    def test_get_stats(self, history_repo):
        history_repo.add(
            url="https://youtube.com/v1",
            title="V1",
            platform="YouTube",
            media_type="video",
            quality="1080p",
            file_path="/tmp/v1.mp4",
            file_size=1000000,
        )
        history_repo.add(
            url="https://youtube.com/v2",
            title="V2",
            platform="YouTube",
            media_type="audio",
            quality="mp3 192kbps",
            file_path="/tmp/v2.mp3",
            file_size=5000000,
        )
        history_repo.add(
            url="https://tiktok.com/v3",
            title="V3",
            platform="TikTok",
            media_type="video",
            quality="720p",
            file_path="/tmp/v3.mp4",
            file_size=2000000,
        )

        stats = history_repo.get_stats()
        assert stats["total_downloads"] == 3
        assert stats["total_size_bytes"] == 8000000
        assert stats["by_platform"]["YouTube"] == 2
        assert stats["by_platform"]["TikTok"] == 1
        assert stats["by_type"]["video"] == 2
        assert stats["by_type"]["audio"] == 1
        assert len(stats["recent"]) == 3

    def test_log_settings_change(self, history_repo):
        history_repo.log_settings_change("download_path", "/old/path", "/new/path")
        history_repo.log_settings_change("retry_attempts", "3", "5")

        changes = history_repo.get_settings_history()
        assert len(changes) == 2
        assert changes[0].key == "retry_attempts"
        assert changes[0].new_value == "5"

    def test_compute_url_hash(self, history_repo):
        url = "https://test.com/video"
        hash1 = history_repo._compute_url_hash(url)
        hash2 = history_repo._compute_url_hash(url)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex

    def test_compute_file_hash(self, history_repo, temp_dir):
        test_file = temp_dir / "test.mp4"
        test_file.write_bytes(b"test content for hashing")

        file_hash = history_repo._compute_file_hash(test_file)
        assert file_hash is not None
        assert len(file_hash) == 64

        # Non-existent file
        assert history_repo._compute_file_hash(temp_dir / "nonexistent") is None
