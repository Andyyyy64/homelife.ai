"""Tests for daemon.storage.database — Database with schema, migrations, CRUD."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from daemon.storage.database import Database
from daemon.storage.models import Event, Frame, Report, SceneType, Summary


@pytest.fixture
def db(tmp_path):
    """Create a fresh Database in a temp directory."""
    db_path = tmp_path / "test.db"
    return Database(db_path)


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

class TestSchemaCreation:
    def test_database_creates_successfully(self, db):
        """Database should initialize without errors."""
        assert db is not None

    def test_frames_table_exists(self, db):
        rows = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='frames'"
        ).fetchall()
        assert len(rows) == 1

    def test_events_table_exists(self, db):
        rows = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
        ).fetchall()
        assert len(rows) == 1

    def test_summaries_table_exists(self, db):
        rows = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='summaries'"
        ).fetchall()
        assert len(rows) == 1

    def test_reports_table_exists(self, db):
        rows = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='reports'"
        ).fetchall()
        assert len(rows) == 1

    def test_activity_mappings_table_exists(self, db):
        rows = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='activity_mappings'"
        ).fetchall()
        assert len(rows) == 1

    def test_window_events_table_exists(self, db):
        rows = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='window_events'"
        ).fetchall()
        assert len(rows) == 1

    def test_memos_table_exists(self, db):
        rows = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memos'"
        ).fetchall()
        assert len(rows) == 1

    def test_chat_messages_table_exists(self, db):
        rows = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_messages'"
        ).fetchall()
        assert len(rows) == 1

    def test_knowledge_table_exists(self, db):
        rows = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge'"
        ).fetchall()
        assert len(rows) == 1

    def test_fts_tables_exist(self, db):
        fts_tables = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_fts'"
        ).fetchall()
        names = {r["name"] for r in fts_tables}
        assert "frames_fts" in names
        assert "summaries_fts" in names

    def test_frames_has_expected_columns(self, db):
        cols = {r["name"] for r in db._conn.execute("PRAGMA table_info(frames)").fetchall()}
        expected = {
            "id", "timestamp", "path", "screen_path", "audio_path",
            "transcription", "brightness", "motion_score", "scene_type",
            "claude_description", "activity", "screen_extra_paths",
            "foreground_window", "pose_data",
        }
        assert expected.issubset(cols)


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

class TestMigrations:
    def test_migrations_idempotent(self, tmp_path):
        """Running migrations twice should not error."""
        db_path = tmp_path / "migrate_test.db"
        db1 = Database(db_path)
        db1.close()
        # Re-open — migrations run again
        db2 = Database(db_path)
        db2.close()

    def test_wal_mode_enabled(self, db):
        row = db._conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"


# ---------------------------------------------------------------------------
# insert_frame / get_frames
# ---------------------------------------------------------------------------

class TestFrameCRUD:
    def _make_frame(self, **kwargs) -> Frame:
        defaults = {
            "timestamp": datetime(2025, 1, 15, 10, 30, 0),
            "path": "frames/test.jpg",
            "screen_path": "screens/test.png",
            "audio_path": "audio/test.wav",
            "transcription": "hello world",
            "brightness": 120.0,
            "motion_score": 0.05,
            "scene_type": SceneType.NORMAL,
            "claude_description": "A person sitting at a desk",
            "activity": "programming",
            "foreground_window": "code.exe|main.py",
        }
        defaults.update(kwargs)
        return Frame(**defaults)

    def test_insert_and_retrieve(self, db):
        frame = self._make_frame()
        frame_id = db.insert_frame(frame)

        assert isinstance(frame_id, int)
        assert frame_id > 0

    def test_get_frames_for_date(self, db):
        frame = self._make_frame(timestamp=datetime(2025, 1, 15, 10, 30, 0))
        db.insert_frame(frame)

        frames = db.get_frames_for_date(date(2025, 1, 15))
        assert len(frames) == 1
        assert frames[0].path == "frames/test.jpg"
        assert frames[0].screen_path == "screens/test.png"
        assert frames[0].transcription == "hello world"
        assert frames[0].activity == "programming"
        assert frames[0].foreground_window == "code.exe|main.py"
        assert frames[0].scene_type == SceneType.NORMAL

    def test_get_frames_for_wrong_date(self, db):
        frame = self._make_frame(timestamp=datetime(2025, 1, 15, 10, 30, 0))
        db.insert_frame(frame)

        frames = db.get_frames_for_date(date(2025, 1, 16))
        assert len(frames) == 0

    def test_multiple_frames(self, db):
        for hour in range(8, 12):
            frame = self._make_frame(
                timestamp=datetime(2025, 1, 15, hour, 0, 0),
                path=f"frames/test_{hour}.jpg",
            )
            db.insert_frame(frame)

        frames = db.get_frames_for_date(date(2025, 1, 15))
        assert len(frames) == 4
        # Should be ordered by timestamp
        assert frames[0].timestamp < frames[-1].timestamp

    def test_get_latest_frame(self, db):
        db.insert_frame(self._make_frame(timestamp=datetime(2025, 1, 15, 9, 0, 0), path="a.jpg"))
        db.insert_frame(self._make_frame(timestamp=datetime(2025, 1, 15, 11, 0, 0), path="b.jpg"))

        latest = db.get_latest_frame()
        assert latest is not None
        assert latest.path == "b.jpg"

    def test_get_latest_frame_empty_db(self, db):
        assert db.get_latest_frame() is None

    def test_get_recent_frames(self, db):
        for hour in range(8, 14):
            db.insert_frame(self._make_frame(
                timestamp=datetime(2025, 1, 15, hour, 0, 0),
                path=f"frames/{hour}.jpg",
            ))

        recent = db.get_recent_frames(limit=3)
        assert len(recent) == 3
        # get_recent_frames reverses the DESC query so result is chronological
        assert recent[0].timestamp < recent[-1].timestamp

    def test_get_frame_count_for_date(self, db):
        for i in range(5):
            db.insert_frame(self._make_frame(
                timestamp=datetime(2025, 1, 15, 10, i, 0),
                path=f"frames/{i}.jpg",
            ))

        count = db.get_frame_count_for_date(date(2025, 1, 15))
        assert count == 5

    def test_get_frames_since(self, db):
        db.insert_frame(self._make_frame(timestamp=datetime(2025, 1, 15, 8, 0, 0), path="early.jpg"))
        db.insert_frame(self._make_frame(timestamp=datetime(2025, 1, 15, 12, 0, 0), path="late.jpg"))

        frames = db.get_frames_since(datetime(2025, 1, 15, 10, 0, 0))
        assert len(frames) == 1
        assert frames[0].path == "late.jpg"

    def test_update_frame_analysis(self, db):
        frame_id = db.insert_frame(self._make_frame())
        db.update_frame_analysis(frame_id, "Updated description", "reading")

        frames = db.get_frames_for_date(date(2025, 1, 15))
        assert frames[0].claude_description == "Updated description"
        assert frames[0].activity == "reading"


# ---------------------------------------------------------------------------
# insert_summary / get_summaries
# ---------------------------------------------------------------------------

class TestSummaryCRUD:
    def _make_summary(self, **kwargs) -> Summary:
        defaults = {
            "timestamp": datetime(2025, 1, 15, 11, 0, 0),
            "scale": "10m",
            "content": "User was programming for 10 minutes",
            "frame_count": 3,
        }
        defaults.update(kwargs)
        return Summary(**defaults)

    def test_insert_and_retrieve(self, db):
        summary = self._make_summary()
        summary_id = db.insert_summary(summary)

        assert isinstance(summary_id, int)
        assert summary_id > 0

    def test_get_summaries_for_date(self, db):
        db.insert_summary(self._make_summary())

        summaries = db.get_summaries_for_date(date(2025, 1, 15))
        assert len(summaries) == 1
        assert summaries[0].scale == "10m"
        assert summaries[0].content == "User was programming for 10 minutes"
        assert summaries[0].frame_count == 3

    def test_get_summaries_filtered_by_scale(self, db):
        db.insert_summary(self._make_summary(scale="10m"))
        db.insert_summary(self._make_summary(scale="30m", content="Half hour summary"))

        summaries_10m = db.get_summaries_for_date(date(2025, 1, 15), scale="10m")
        assert len(summaries_10m) == 1
        assert summaries_10m[0].scale == "10m"

        summaries_30m = db.get_summaries_for_date(date(2025, 1, 15), scale="30m")
        assert len(summaries_30m) == 1
        assert summaries_30m[0].scale == "30m"

    def test_get_latest_summary(self, db):
        db.insert_summary(self._make_summary(
            timestamp=datetime(2025, 1, 15, 10, 0, 0), content="First",
        ))
        db.insert_summary(self._make_summary(
            timestamp=datetime(2025, 1, 15, 11, 0, 0), content="Second",
        ))

        latest = db.get_latest_summary("10m")
        assert latest is not None
        assert latest.content == "Second"

    def test_get_latest_summary_empty(self, db):
        assert db.get_latest_summary("10m") is None

    def test_get_summaries_since(self, db):
        db.insert_summary(self._make_summary(
            timestamp=datetime(2025, 1, 15, 8, 0, 0), content="Early",
        ))
        db.insert_summary(self._make_summary(
            timestamp=datetime(2025, 1, 15, 12, 0, 0), content="Late",
        ))

        results = db.get_summaries_since(datetime(2025, 1, 15, 10, 0, 0), "10m")
        assert len(results) == 1
        assert results[0].content == "Late"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEventCRUD:
    def test_insert_and_retrieve(self, db):
        event = Event(
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            event_type="motion_spike",
            description="High motion detected",
            frame_id=None,
        )
        event_id = db.insert_event(event)
        assert isinstance(event_id, int)

        events = db.get_events_for_date(date(2025, 1, 15))
        assert len(events) == 1
        assert events[0].event_type == "motion_spike"
        assert events[0].description == "High motion detected"


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class TestReportCRUD:
    def test_insert_and_retrieve(self, db):
        report = Report(
            date="2025-01-15",
            content="Daily report content",
            generated_at=datetime(2025, 1, 15, 23, 0, 0),
            frame_count=100,
            focus_pct=65.5,
        )
        report_id = db.insert_report(report)
        assert isinstance(report_id, int)

        result = db.get_report(date(2025, 1, 15))
        assert result is not None
        assert result.content == "Daily report content"
        assert result.frame_count == 100
        assert result.focus_pct == pytest.approx(65.5)

    def test_get_report_not_found(self, db):
        assert db.get_report(date(2025, 6, 1)) is None

    def test_report_upsert(self, db):
        report1 = Report(
            date="2025-01-15", content="First",
            generated_at=datetime(2025, 1, 15, 22, 0, 0),
            frame_count=50, focus_pct=50.0,
        )
        report2 = Report(
            date="2025-01-15", content="Updated",
            generated_at=datetime(2025, 1, 15, 23, 0, 0),
            frame_count=100, focus_pct=70.0,
        )
        db.insert_report(report1)
        db.insert_report(report2)

        result = db.get_report(date(2025, 1, 15))
        assert result.content == "Updated"

    def test_get_reports_list(self, db):
        for day in range(1, 4):
            db.insert_report(Report(
                date=f"2025-01-{day:02d}",
                content=f"Report {day}",
                generated_at=datetime(2025, 1, day, 23, 0, 0),
                frame_count=10, focus_pct=50.0,
            ))

        reports = db.get_reports(limit=10)
        assert len(reports) == 3
        # Should be ordered by date DESC
        assert reports[0].date == "2025-01-03"


# ---------------------------------------------------------------------------
# Activity mappings
# ---------------------------------------------------------------------------

class TestActivityMappings:
    def test_upsert_and_get_all(self, db):
        db.upsert_activity_mapping("programming", "focus")
        db.upsert_activity_mapping("browsing", "browsing")

        mappings = db.get_all_activity_mappings()
        activities = {m["activity"] for m in mappings}
        assert "programming" in activities
        assert "browsing" in activities

    def test_upsert_increments_count(self, db):
        db.upsert_activity_mapping("programming", "focus")
        db.upsert_activity_mapping("programming", "focus")

        mappings = db.get_all_activity_mappings()
        prog = next(m for m in mappings if m["activity"] == "programming")
        assert prog["frame_count"] == 2

    def test_get_frequent_activities(self, db):
        db.upsert_activity_mapping("programming", "focus")
        db.upsert_activity_mapping("programming", "focus")
        db.upsert_activity_mapping("browsing", "browsing")

        frequent = db.get_frequent_activities(limit=10)
        assert frequent[0] == "programming"

    def test_merge_activity(self, db):
        # Insert a frame with the old activity
        frame = Frame(
            timestamp=datetime(2025, 1, 15, 10, 0, 0),
            path="test.jpg", activity="coding",
        )
        db.insert_frame(frame)
        db.upsert_activity_mapping("coding", "focus")

        db.merge_activity("coding", "programming")

        # The frame's activity should be updated
        frames = db.get_frames_for_date(date(2025, 1, 15))
        assert frames[0].activity == "programming"

        # The old mapping should be gone
        mappings = db.get_all_activity_mappings()
        activities = {m["activity"] for m in mappings}
        assert "coding" not in activities
        assert "programming" in activities


# ---------------------------------------------------------------------------
# Memos
# ---------------------------------------------------------------------------

class TestMemoCRUD:
    def test_get_memo_empty(self, db):
        assert db.get_memo(date(2025, 1, 15)) == ""

    def test_upsert_and_get_memo(self, db):
        db.upsert_memo(date(2025, 1, 15), "Today's goals: finish tests")
        assert db.get_memo(date(2025, 1, 15)) == "Today's goals: finish tests"

    def test_memo_update(self, db):
        db.upsert_memo(date(2025, 1, 15), "First")
        db.upsert_memo(date(2025, 1, 15), "Updated")
        assert db.get_memo(date(2025, 1, 15)) == "Updated"


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------

class TestClose:
    def test_close_without_error(self, db):
        db.close()
