"""Tests for daemon.retention — Data retention and cleanup."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from daemon.retention import cleanup_old_data
from daemon.storage.database import Database
from daemon.storage.models import Event, Frame, Report, Summary


@pytest.fixture
def db(tmp_path):
    """Create a fresh Database in a temp directory."""
    db_path = tmp_path / "test.db"
    return Database(db_path)


@pytest.fixture
def data_dir(tmp_path):
    """Create a data directory with subdirectories for media files."""
    d = tmp_path / "data"
    (d / "frames").mkdir(parents=True)
    (d / "screens").mkdir(parents=True)
    (d / "audio").mkdir(parents=True)
    return d


def _create_media_file(data_dir: Path, rel_path: str, size: int = 1024) -> Path:
    """Create a dummy media file and return its absolute path."""
    abs_path = data_dir / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(b"\x00" * size)
    return abs_path


# ---------------------------------------------------------------------------
# Basic cleanup
# ---------------------------------------------------------------------------

class TestCleanupOldData:
    def test_deletes_old_frames(self, db, data_dir):
        """Frames older than retention_days should be deleted."""
        old_ts = datetime.now() - timedelta(days=100)
        new_ts = datetime.now() - timedelta(days=10)

        db.insert_frame(Frame(timestamp=old_ts, path="frames/old.jpg"))
        db.insert_frame(Frame(timestamp=new_ts, path="frames/new.jpg"))

        result = cleanup_old_data(db, data_dir, retention_days=90)

        assert result["frames_deleted"] == 1
        # Only the new frame should remain
        remaining = db._conn.execute("SELECT COUNT(*) as cnt FROM frames").fetchone()
        assert remaining["cnt"] == 1

    def test_deletes_old_summaries(self, db, data_dir):
        """Summaries older than retention_days should be deleted."""
        old_ts = datetime.now() - timedelta(days=100)
        new_ts = datetime.now() - timedelta(days=10)

        db.insert_summary(Summary(timestamp=old_ts, scale="10m", content="old", frame_count=5))
        db.insert_summary(Summary(timestamp=new_ts, scale="10m", content="new", frame_count=3))

        result = cleanup_old_data(db, data_dir, retention_days=90)

        assert result["summaries_deleted"] == 1
        remaining = db._conn.execute("SELECT COUNT(*) as cnt FROM summaries").fetchone()
        assert remaining["cnt"] == 1

    def test_deletes_old_events(self, db, data_dir):
        """Events older than retention_days should be deleted."""
        old_ts = datetime.now() - timedelta(days=100)
        new_ts = datetime.now() - timedelta(days=10)

        db.insert_event(Event(timestamp=old_ts, event_type="motion_spike", description="old"))
        db.insert_event(Event(timestamp=new_ts, event_type="motion_spike", description="new"))

        result = cleanup_old_data(db, data_dir, retention_days=90)

        assert result["events_deleted"] == 1
        remaining = db._conn.execute("SELECT COUNT(*) as cnt FROM events").fetchone()
        assert remaining["cnt"] == 1

    def test_keeps_reports(self, db, data_dir):
        """Reports should never be deleted by retention cleanup."""
        old_date = (datetime.now() - timedelta(days=200)).date()
        db.insert_report(Report(
            date=old_date.isoformat(),
            content="Very old report",
            generated_at=datetime.now() - timedelta(days=200),
            frame_count=50,
            focus_pct=70.0,
        ))

        cleanup_old_data(db, data_dir, retention_days=90)

        report = db.get_report(old_date)
        assert report is not None
        assert report.content == "Very old report"


# ---------------------------------------------------------------------------
# File cleanup
# ---------------------------------------------------------------------------

class TestFileCleanup:
    def test_removes_frame_files(self, db, data_dir):
        """Media files referenced by old frames should be deleted from disk."""
        old_ts = datetime.now() - timedelta(days=100)

        _create_media_file(data_dir, "frames/old.jpg", size=2048)
        _create_media_file(data_dir, "screens/old.png", size=4096)
        _create_media_file(data_dir, "audio/old.wav", size=8192)

        db.insert_frame(Frame(
            timestamp=old_ts,
            path="frames/old.jpg",
            screen_path="screens/old.png",
            audio_path="audio/old.wav",
        ))

        result = cleanup_old_data(db, data_dir, retention_days=90)

        assert result["files_deleted"] == 3
        assert result["freed_bytes"] == 2048 + 4096 + 8192
        assert not (data_dir / "frames/old.jpg").exists()
        assert not (data_dir / "screens/old.png").exists()
        assert not (data_dir / "audio/old.wav").exists()

    def test_keeps_new_files(self, db, data_dir):
        """Files referenced by recent frames should not be deleted."""
        new_ts = datetime.now() - timedelta(days=10)

        _create_media_file(data_dir, "frames/new.jpg", size=1024)

        db.insert_frame(Frame(
            timestamp=new_ts,
            path="frames/new.jpg",
        ))

        result = cleanup_old_data(db, data_dir, retention_days=90)

        assert result["files_deleted"] == 0
        assert (data_dir / "frames/new.jpg").exists()

    def test_handles_missing_files(self, db, data_dir):
        """Cleanup should not fail if referenced files are already gone."""
        old_ts = datetime.now() - timedelta(days=100)

        db.insert_frame(Frame(
            timestamp=old_ts,
            path="frames/missing.jpg",
            screen_path="screens/missing.png",
        ))

        # No files on disk — should still succeed
        result = cleanup_old_data(db, data_dir, retention_days=90)

        assert result["frames_deleted"] == 1
        assert result["files_deleted"] == 0

    def test_handles_screen_extra_paths(self, db, data_dir):
        """Extra screen captures (comma-separated) should also be cleaned up."""
        old_ts = datetime.now() - timedelta(days=100)

        _create_media_file(data_dir, "screens/extra1.png", size=1024)
        _create_media_file(data_dir, "screens/extra2.png", size=1024)

        db.insert_frame(Frame(
            timestamp=old_ts,
            path="",
            screen_extra_paths="screens/extra1.png,screens/extra2.png",
        ))

        result = cleanup_old_data(db, data_dir, retention_days=90)

        assert result["files_deleted"] == 2
        assert not (data_dir / "screens/extra1.png").exists()
        assert not (data_dir / "screens/extra2.png").exists()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_database(self, db, data_dir):
        """Cleanup on an empty database should not fail."""
        result = cleanup_old_data(db, data_dir, retention_days=90)

        assert result["frames_deleted"] == 0
        assert result["summaries_deleted"] == 0
        assert result["events_deleted"] == 0
        assert result["files_deleted"] == 0
        assert result["freed_bytes"] == 0

    def test_nothing_old_enough(self, db, data_dir):
        """Nothing should be deleted if all data is within retention."""
        recent_ts = datetime.now() - timedelta(days=30)

        db.insert_frame(Frame(timestamp=recent_ts, path="frames/recent.jpg"))
        db.insert_summary(Summary(timestamp=recent_ts, scale="1h", content="test", frame_count=1))
        db.insert_event(Event(timestamp=recent_ts, event_type="test", description="test"))

        result = cleanup_old_data(db, data_dir, retention_days=90)

        assert result["frames_deleted"] == 0
        assert result["summaries_deleted"] == 0
        assert result["events_deleted"] == 0

    def test_short_retention(self, db, data_dir):
        """A short retention period (e.g. 1 day) should work."""
        yesterday_ts = datetime.now() - timedelta(days=2)

        _create_media_file(data_dir, "frames/yesterday.jpg", size=512)
        db.insert_frame(Frame(timestamp=yesterday_ts, path="frames/yesterday.jpg"))

        result = cleanup_old_data(db, data_dir, retention_days=1)

        assert result["frames_deleted"] == 1
        assert result["files_deleted"] == 1

    def test_empty_paths_ignored(self, db, data_dir):
        """Frames with empty path fields should not cause errors."""
        old_ts = datetime.now() - timedelta(days=100)

        db.insert_frame(Frame(
            timestamp=old_ts,
            path="",
            screen_path="",
            audio_path="",
            screen_extra_paths="",
        ))

        result = cleanup_old_data(db, data_dir, retention_days=90)

        assert result["frames_deleted"] == 1
        assert result["files_deleted"] == 0

    def test_return_value_structure(self, db, data_dir):
        """The returned dict should have all expected keys."""
        result = cleanup_old_data(db, data_dir, retention_days=90)

        assert "frames_deleted" in result
        assert "summaries_deleted" in result
        assert "events_deleted" in result
        assert "window_events_deleted" in result
        assert "files_deleted" in result
        assert "freed_bytes" in result
