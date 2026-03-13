"""Tests for daemon.embedding — Multimodal Embedder + sqlite-vec unified vector store."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from daemon.embedding import Embedder
from daemon.storage.database import Database
from daemon.storage.models import ChatMessage, Frame, SceneType, Summary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DIMS = 8  # small dimension for tests


def _fake_embedding(dims: int = DIMS, seed: float = 0.0) -> list[float]:
    return [seed + float(i) / dims for i in range(dims)]


def _make_frame(**kwargs) -> Frame:
    defaults = {
        "id": 1,
        "timestamp": datetime(2025, 1, 15, 10, 30, 0),
        "path": "frames/2025-01-15/10-30-00.jpg",
        "screen_path": "screens/2025-01-15/10-30-00.png",
        "audio_path": "audio/2025-01-15/10-30-00.wav",
        "transcription": "hello world",
        "brightness": 120.0,
        "motion_score": 0.05,
        "scene_type": SceneType.NORMAL,
        "claude_description": "User is programming in VS Code",
        "activity": "programming",
        "foreground_window": "code.exe|main.py",
    }
    defaults.update(kwargs)
    return Frame(**defaults)


def _make_chat(**kwargs) -> ChatMessage:
    defaults = {
        "id": 1,
        "platform": "discord",
        "platform_message_id": "msg_001",
        "channel_id": "ch_123",
        "channel_name": "general",
        "guild_id": "guild_1",
        "guild_name": "MyServer",
        "author_id": "user_1",
        "author_name": "Alice",
        "is_self": False,
        "content": "Hey, check out this new feature!",
        "timestamp": datetime(2025, 1, 15, 10, 30, 0),
        "metadata": "",
    }
    defaults.update(kwargs)
    return ChatMessage(**defaults)


def _make_summary(**kwargs) -> Summary:
    defaults = {
        "id": 1,
        "timestamp": datetime(2025, 1, 15, 11, 0, 0),
        "scale": "10m",
        "content": "User was programming for 10 minutes in VS Code",
        "frame_count": 3,
    }
    defaults.update(kwargs)
    return Summary(**defaults)


def _setup_data_dir(tmp_path: Path, frame: Frame) -> Path:
    data_dir = tmp_path / "data"
    if frame.path:
        p = data_dir / frame.path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\xff\xd8\xff\xe0JFIF_FAKE_JPEG")
    if frame.screen_path:
        p = data_dir / frame.screen_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x89PNG\r\n\x1a\nFAKE_PNG")
    if frame.audio_path:
        p = data_dir / frame.audio_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt FAKE_WAV")
    return data_dir


def _mock_embed_response(dims: int = DIMS):
    embedding_obj = MagicMock()
    embedding_obj.values = _fake_embedding(dims)
    resp = MagicMock()
    resp.embeddings = [embedding_obj]
    return resp


def _mock_embedder(dims: int = DIMS) -> Embedder:
    embedder = Embedder(dimensions=dims)
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = _mock_embed_response(dims)
    embedder._client = mock_client
    return embedder


# ---------------------------------------------------------------------------
# Frame embedding — content assembly (all modalities)
# ---------------------------------------------------------------------------


class TestFrameEmbedding:
    def test_all_modalities_included(self, tmp_path):
        """Camera, screen, audio, and text should all be in one Content."""
        frame = _make_frame()
        data_dir = _setup_data_dir(tmp_path, frame)
        embedder = _mock_embedder()

        result = embedder.embed_frame(frame, data_dir)
        assert result is not None
        assert len(result) == DIMS

        call_kwargs = embedder._client.models.embed_content.call_args.kwargs
        parts = call_kwargs["contents"][0].parts
        # camera + screen + audio + text = 4 parts
        assert len(parts) >= 4

    def test_camera_only(self, tmp_path):
        frame = _make_frame(screen_path="", audio_path="", transcription="",
                            claude_description="", activity="", foreground_window="")
        data_dir = _setup_data_dir(tmp_path, frame)
        embedder = _mock_embedder()

        result = embedder.embed_frame(frame, data_dir)
        assert result is not None
        parts = embedder._client.models.embed_content.call_args.kwargs["contents"][0].parts
        assert len(parts) == 1

    def test_screen_only(self, tmp_path):
        frame = _make_frame(path="", audio_path="", transcription="",
                            claude_description="", activity="", foreground_window="")
        data_dir = _setup_data_dir(tmp_path, frame)
        embedder = _mock_embedder()

        result = embedder.embed_frame(frame, data_dir)
        assert result is not None

    def test_audio_only(self, tmp_path):
        frame = _make_frame(path="", screen_path="", transcription="",
                            claude_description="", activity="", foreground_window="")
        data_dir = _setup_data_dir(tmp_path, frame)
        embedder = _mock_embedder()

        result = embedder.embed_frame(frame, data_dir)
        assert result is not None

    def test_text_metadata_content(self, tmp_path):
        frame = _make_frame(path="", screen_path="", audio_path="")
        data_dir = _setup_data_dir(tmp_path, frame)
        embedder = _mock_embedder()

        embedder.embed_frame(frame, data_dir)
        parts = embedder._client.models.embed_content.call_args.kwargs["contents"][0].parts
        text = parts[0].text
        assert "User is programming in VS Code" in text
        assert "Activity: programming" in text
        assert "Transcription: hello world" in text
        assert "Window: code.exe|main.py" in text

    def test_empty_frame_returns_none(self, tmp_path):
        frame = _make_frame(path="", screen_path="", audio_path="",
                            transcription="", claude_description="", activity="", foreground_window="")
        data_dir = _setup_data_dir(tmp_path, frame)
        embedder = _mock_embedder()

        result = embedder.embed_frame(frame, data_dir)
        assert result is None

    def test_missing_files_skipped(self, tmp_path):
        frame = _make_frame()
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        embedder = _mock_embedder()

        result = embedder.embed_frame(frame, data_dir)
        assert result is not None  # text metadata still embeds

    def test_task_type_is_retrieval_document(self, tmp_path):
        frame = _make_frame(path="", screen_path="", audio_path="")
        data_dir = _setup_data_dir(tmp_path, frame)
        embedder = _mock_embedder()

        embedder.embed_frame(frame, data_dir)
        config = embedder._client.models.embed_content.call_args.kwargs["config"]
        assert config.task_type == "RETRIEVAL_DOCUMENT"


# ---------------------------------------------------------------------------
# Chat message embedding
# ---------------------------------------------------------------------------


class TestChatEmbedding:
    def test_chat_message_embedded(self):
        msg = _make_chat()
        embedder = _mock_embedder()

        result = embedder.embed_chat_message(msg)
        assert result is not None
        assert len(result) == DIMS

    def test_chat_includes_context(self):
        msg = _make_chat(platform="discord", channel_name="general", author_name="Alice",
                         content="Let's deploy tomorrow")
        embedder = _mock_embedder()

        embedder.embed_chat_message(msg)
        text = embedder._client.models.embed_content.call_args.kwargs["contents"]
        assert "discord/general" in text
        assert "Alice:" in text
        assert "Let's deploy tomorrow" in text

    def test_chat_empty_content_returns_none(self):
        msg = _make_chat(content="")
        embedder = _mock_embedder()

        result = embedder.embed_chat_message(msg)
        assert result is None

    def test_chat_task_type_is_document(self):
        msg = _make_chat()
        embedder = _mock_embedder()

        embedder.embed_chat_message(msg)
        config = embedder._client.models.embed_content.call_args.kwargs["config"]
        assert config.task_type == "RETRIEVAL_DOCUMENT"

    def test_chat_no_channel_name(self):
        msg = _make_chat(channel_name="", author_name="Bob", content="Hello")
        embedder = _mock_embedder()

        embedder.embed_chat_message(msg)
        text = embedder._client.models.embed_content.call_args.kwargs["contents"]
        assert "Bob:" in text
        assert "Hello" in text


# ---------------------------------------------------------------------------
# Summary embedding
# ---------------------------------------------------------------------------


class TestSummaryEmbedding:
    def test_summary_embedded(self):
        summary = _make_summary()
        embedder = _mock_embedder()

        result = embedder.embed_summary(summary)
        assert result is not None

    def test_summary_includes_scale(self):
        summary = _make_summary(scale="1h", content="Focused coding session")
        embedder = _mock_embedder()

        embedder.embed_summary(summary)
        text = embedder._client.models.embed_content.call_args.kwargs["contents"]
        assert "1h summary" in text
        assert "Focused coding session" in text

    def test_summary_empty_returns_none(self):
        summary = _make_summary(content="")
        embedder = _mock_embedder()

        result = embedder.embed_summary(summary)
        assert result is None

    def test_summary_task_type_is_document(self):
        summary = _make_summary()
        embedder = _mock_embedder()

        embedder.embed_summary(summary)
        config = embedder._client.models.embed_content.call_args.kwargs["config"]
        assert config.task_type == "RETRIEVAL_DOCUMENT"


# ---------------------------------------------------------------------------
# Search query embedding
# ---------------------------------------------------------------------------


class TestSearchQueryEmbedding:
    def test_embed_text_query(self):
        embedder = _mock_embedder()

        result = embedder.embed_text("what was I doing yesterday?")
        assert result is not None

    def test_query_task_type_is_retrieval_query(self):
        embedder = _mock_embedder()

        embedder.embed_text("test query")
        config = embedder._client.models.embed_content.call_args.kwargs["config"]
        assert config.task_type == "RETRIEVAL_QUERY"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestEmbedderErrors:
    def test_no_api_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        embedder = Embedder(dimensions=DIMS)
        embedder._client = None

        assert embedder.embed_text("test") is None
        assert embedder.embed_chat_message(_make_chat()) is None
        assert embedder.embed_summary(_make_summary()) is None

    def test_api_error_returns_none(self, tmp_path):
        frame = _make_frame(path="", screen_path="", audio_path="")
        data_dir = _setup_data_dir(tmp_path, frame)
        embedder = Embedder(dimensions=DIMS)
        mock_client = MagicMock()
        mock_client.models.embed_content.side_effect = Exception("API error 500")
        embedder._client = mock_client

        assert embedder.embed_frame(frame, data_dir) is None
        assert embedder.embed_chat_message(_make_chat()) is None
        assert embedder.embed_summary(_make_summary()) is None
        assert embedder.embed_text("test") is None


# ---------------------------------------------------------------------------
# Unified vec_items + vec_items_meta — DB layer
# ---------------------------------------------------------------------------


class TestUnifiedVecTable:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(tmp_path / "test.db", embedding_dimensions=DIMS)

    def test_tables_created(self, db):
        assert db._vec_enabled is True
        # vec_items_meta should exist as regular table
        row = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vec_items_meta'"
        ).fetchone()
        assert row is not None

    def test_insert_frame_embedding(self, db):
        db.insert_embedding("frame", 1, "2025-01-15T10:30:00", "programming", _fake_embedding())
        assert db.get_embedding_count() == 1
        assert db.get_embedding_count("frame") == 1

    def test_insert_chat_embedding(self, db):
        db.insert_embedding("chat", 42, "2025-01-15T10:30:00", "Alice: hello", _fake_embedding())
        assert db.get_embedding_count("chat") == 1

    def test_insert_summary_embedding(self, db):
        db.insert_embedding("summary", 5, "2025-01-15T11:00:00", "[10m] coding session", _fake_embedding())
        assert db.get_embedding_count("summary") == 1

    def test_mixed_types_counted(self, db):
        db.insert_embedding("frame", 1, "2025-01-15T10:30:00", "frame", _fake_embedding(seed=0.1))
        db.insert_embedding("chat", 1, "2025-01-15T10:30:00", "chat", _fake_embedding(seed=0.2))
        db.insert_embedding("summary", 1, "2025-01-15T11:00:00", "summary", _fake_embedding(seed=0.3))

        assert db.get_embedding_count() == 3
        assert db.get_embedding_count("frame") == 1
        assert db.get_embedding_count("chat") == 1
        assert db.get_embedding_count("summary") == 1

    def test_upsert_replaces(self, db):
        db.insert_embedding("frame", 1, "2025-01-15T10:30:00", "v1", [1.0] * DIMS)
        db.insert_embedding("frame", 1, "2025-01-15T10:30:00", "v2", [2.0] * DIMS)
        assert db.get_embedding_count("frame") == 1


# ---------------------------------------------------------------------------
# KNN search — unified
# ---------------------------------------------------------------------------


class TestUnifiedSearch:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(tmp_path / "test.db", embedding_dimensions=DIMS)

    def test_search_all_types(self, db):
        v_frame = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        v_chat = [0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        v_summary = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]

        db.insert_embedding("frame", 10, "2025-01-15T10:30:00", "coding", v_frame)
        db.insert_embedding("chat", 20, "2025-01-15T10:30:00", "Alice: code review", v_chat)
        db.insert_embedding("summary", 30, "2025-01-15T11:00:00", "summary", v_summary)

        query = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        results = db.search_similar(query, limit=3)

        assert len(results) == 3
        # frame should be closest (exact match)
        assert results[0]["item_type"] == "frame"
        assert results[0]["source_id"] == 10
        assert results[0]["distance"] == pytest.approx(0.0, abs=1e-5)
        # chat should be second
        assert results[1]["item_type"] == "chat"
        # summary should be last (orthogonal)
        assert results[2]["item_type"] == "summary"

    def test_search_filter_by_type(self, db):
        v1 = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        v2 = [0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        db.insert_embedding("frame", 1, "2025-01-15T10:30:00", "frame1", v1)
        db.insert_embedding("chat", 1, "2025-01-15T10:30:00", "chat1", v2)

        query = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        results = db.search_similar(query, limit=10, item_type="chat")

        assert len(results) == 1
        assert results[0]["item_type"] == "chat"

    def test_search_returns_metadata(self, db):
        db.insert_embedding("frame", 42, "2025-01-15T10:30:00", "coding in VS Code", [0.5] * DIMS)

        results = db.search_similar([0.5] * DIMS, limit=1)
        assert len(results) == 1
        r = results[0]
        assert r["item_type"] == "frame"
        assert r["source_id"] == 42
        assert r["timestamp"] == "2025-01-15T10:30:00"
        assert r["preview"] == "coding in VS Code"
        assert r["distance"] == pytest.approx(0.0, abs=1e-5)

    def test_search_limit(self, db):
        for i in range(10):
            db.insert_embedding("frame", i, f"2025-01-15T{10 + i}:00:00", f"frame {i}", _fake_embedding(seed=float(i)))
        results = db.search_similar(_fake_embedding(), limit=3)
        assert len(results) == 3

    def test_search_empty(self, db):
        assert db.search_similar([0.0] * DIMS, limit=5) == []

    def test_cosine_identical(self, db):
        vec = [0.5, 0.3, 0.1, 0.8, 0.2, 0.6, 0.4, 0.7]
        db.insert_embedding("frame", 1, "2025-01-15T10:30:00", "test", vec)
        results = db.search_similar(vec, limit=1)
        assert results[0]["distance"] == pytest.approx(0.0, abs=1e-5)

    def test_cosine_orthogonal(self, db):
        v1 = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        db.insert_embedding("frame", 1, "2025-01-15T10:30:00", "a", v1)
        results = db.search_similar(v2, limit=1)
        assert results[0]["distance"] == pytest.approx(1.0, abs=1e-3)


# ---------------------------------------------------------------------------
# Unembedded item tracking
# ---------------------------------------------------------------------------


class TestUnembeddedTracking:
    @pytest.fixture
    def db(self, tmp_path):
        return Database(tmp_path / "test.db", embedding_dimensions=DIMS)

    def test_get_unembedded_chat_ids(self, db):
        # Insert some chat messages
        msg1 = _make_chat(id=None, platform_message_id="m1", content="first")
        msg2 = _make_chat(id=None, platform_message_id="m2", content="second")
        id1 = db.insert_chat_message(msg1)
        id2 = db.insert_chat_message(msg2)

        since = datetime(2025, 1, 15, 0, 0, 0)
        unembedded = db.get_unembedded_chat_ids(since, limit=10)
        assert id1 in unembedded
        assert id2 in unembedded

        # Embed one
        db.insert_embedding("chat", id1, "2025-01-15T10:30:00", "msg1", _fake_embedding())

        unembedded = db.get_unembedded_chat_ids(since, limit=10)
        assert id1 not in unembedded
        assert id2 in unembedded

    def test_get_unembedded_summary_ids(self, db):
        s1 = _make_summary(id=None, scale="10m", content="summary 1")
        s2 = _make_summary(id=None, scale="30m", content="summary 2")
        id1 = db.insert_summary(s1)
        id2 = db.insert_summary(s2)

        since = datetime(2025, 1, 15, 0, 0, 0)
        unembedded = db.get_unembedded_summary_ids(since, limit=10)
        assert id1 in unembedded
        assert id2 in unembedded

        # Embed one
        db.insert_embedding("summary", id1, "2025-01-15T11:00:00", "s1", _fake_embedding())

        unembedded = db.get_unembedded_summary_ids(since, limit=10)
        assert id1 not in unembedded
        assert id2 in unembedded


# ---------------------------------------------------------------------------
# Initialization edge cases
# ---------------------------------------------------------------------------


class TestVecInit:
    def test_double_init_idempotent(self, tmp_path):
        db_path = tmp_path / "test.db"
        db1 = Database(db_path, embedding_dimensions=DIMS)
        db1.insert_embedding("frame", 1, "2025-01-15T10:30:00", "test", _fake_embedding())
        db1.close()

        db2 = Database(db_path, embedding_dimensions=DIMS)
        assert db2._vec_enabled is True
        assert db2.get_embedding_count() == 1
        db2.close()

    def test_vec_disabled_without_extension(self, tmp_path):
        import builtins
        real_import = builtins.__import__

        def _block(name, *args, **kwargs):
            if name == "sqlite_vec":
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_block):
            db = Database(tmp_path / "test.db", embedding_dimensions=DIMS)
            assert db._vec_enabled is False
            db.insert_embedding("frame", 1, "t", "p", _fake_embedding())
            assert db.get_embedding_count() == 0
            assert db.search_similar(_fake_embedding()) == []
            db.close()

    def test_invalid_dimensions(self, tmp_path):
        db = Database(tmp_path / "test.db", embedding_dimensions=0)
        assert db._vec_enabled is False
        db.close()


# ---------------------------------------------------------------------------
# E2E: embed → store → cross-type search
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_cross_type_search(self, tmp_path):
        """Search query should find relevant items across frames, chat, and summaries."""
        db = Database(tmp_path / "test.db", embedding_dimensions=DIMS)

        # Frame about coding
        v_coding = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        db.insert_embedding("frame", 1, "2025-01-15T10:30:00", "coding in VS Code", v_coding)

        # Chat about code review (similar direction to coding)
        v_review = [0.85, 0.15, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        db.insert_embedding("chat", 5, "2025-01-15T10:35:00", "Alice: code review done", v_review)

        # Summary about meeting (orthogonal)
        v_meeting = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        db.insert_embedding("summary", 3, "2025-01-15T11:00:00", "[1h] meeting", v_meeting)

        # Chat about lunch (also orthogonal)
        v_lunch = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        db.insert_embedding("chat", 8, "2025-01-15T12:00:00", "Bob: let's get lunch", v_lunch)

        # Query: "coding" → should find frame + code review chat first
        query = [0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        results = db.search_similar(query, limit=4)

        assert len(results) == 4
        # Top 2 should be coding-related (frame + chat)
        top_types = {r["item_type"] for r in results[:2]}
        assert "frame" in top_types
        assert "chat" in top_types

        db.close()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestEmbeddingConfig:
    def test_default_embedding_config(self, tmp_path):
        from daemon.config import Config
        cfg = Config.load(tmp_path / "nonexistent.toml")
        assert cfg.embedding.enabled is True
        assert cfg.embedding.model == "gemini-embedding-2-preview"
        assert cfg.embedding.dimensions == 3072

    def test_load_from_toml(self, tmp_path):
        from daemon.config import Config
        toml_path = tmp_path / "test.toml"
        toml_path.write_text("[embedding]\nenabled = false\nmodel = \"custom\"\ndimensions = 1536\n")
        cfg = Config.load(toml_path)
        assert cfg.embedding.enabled is False
        assert cfg.embedding.model == "custom"
        assert cfg.embedding.dimensions == 1536

    def test_partial_config(self, tmp_path):
        from daemon.config import Config
        toml_path = tmp_path / "test.toml"
        toml_path.write_text("[embedding]\ndimensions = 3072\n")
        cfg = Config.load(toml_path)
        assert cfg.embedding.enabled is True
        assert cfg.embedding.dimensions == 3072
