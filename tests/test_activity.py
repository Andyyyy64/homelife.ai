"""Tests for daemon.activity — ActivityManager, _similarity, _normalize_str."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from daemon.activity import (
    VALID_META_CATEGORIES,
    ActivityManager,
    _normalize_str,
    _similarity,
)

# ---------------------------------------------------------------------------
# _normalize_str
# ---------------------------------------------------------------------------

class TestNormalizeStr:
    def test_strips_whitespace(self):
        assert _normalize_str("  hello  ") == "hello"

    def test_lowercases(self):
        assert _normalize_str("Programming") == "programming"

    def test_unicode_normalization(self):
        # NFKC normalizes full-width to half-width
        assert _normalize_str("\uff30\uff32") == "pr"  # full-width PR -> pr


# ---------------------------------------------------------------------------
# _similarity
# ---------------------------------------------------------------------------

class TestSimilarity:
    def test_identical_strings(self):
        assert _similarity("programming", "programming") == 1.0

    def test_identical_case_insensitive(self):
        assert _similarity("Programming", "programming") == 1.0

    def test_empty_strings(self):
        assert _similarity("", "") == 1.0  # both normalize to same empty

    def test_one_empty(self):
        assert _similarity("hello", "") == 0.0

    def test_lcs_code_coding(self):
        score = _similarity("code", "coding")
        # "code" is NOT a substring of "coding" — LCS = "cod" + "e" via LCS
        assert score == pytest.approx(0.6, abs=0.01)

    def test_lcs_code_coding_reverse(self):
        score = _similarity("coding", "code")
        assert score == pytest.approx(0.6, abs=0.01)

    def test_completely_different(self):
        score = _similarity("abc", "xyz")
        assert score == 0.0

    def test_partial_overlap(self):
        score = _similarity("programming", "program")
        # "program" is substring of "programming" -> 7/11
        assert score == pytest.approx(7.0 / 11.0, abs=0.01)

    def test_japanese_exact_match(self):
        assert _similarity("プログラミング", "プログラミング") == 1.0

    def test_japanese_substring(self):
        score = _similarity("プログラミング", "プログラミングと会話")
        # 7 chars in 10 chars -> 7/10
        assert score == pytest.approx(7.0 / 10.0, abs=0.01)

    def test_lcs_similarity(self):
        # "abcde" vs "aXcXe" -> LCS = "ace" (length 3), ratio = 2*3/(5+5) = 0.6
        score = _similarity("abcde", "aXcXe")
        assert score == pytest.approx(0.6, abs=0.01)

    def test_high_similarity(self):
        score = _similarity("browsing the web", "browsing web")
        assert score > 0.7

    def test_symmetry(self):
        s1 = _similarity("hello world", "world hello")
        s2 = _similarity("world hello", "hello world")
        assert s1 == pytest.approx(s2, abs=0.001)


# ---------------------------------------------------------------------------
# ActivityManager — with mock DB
# ---------------------------------------------------------------------------

def _make_mock_db(mappings: list[dict] | None = None):
    """Create a mock Database with configurable activity_mappings."""
    db = MagicMock()
    if mappings is None:
        mappings = []
    db.get_all_activity_mappings.return_value = mappings
    db.get_frequent_activities.return_value = [m["activity"] for m in mappings[:15]]
    return db


class TestActivityManagerInit:
    def test_loads_cache_from_db(self):
        mappings = [
            {"activity": "programming", "meta_category": "focus", "frame_count": 10},
            {"activity": "browsing", "meta_category": "browsing", "frame_count": 5},
        ]
        db = _make_mock_db(mappings)
        mgr = ActivityManager(db)

        assert mgr._cache == {"programming": "focus", "browsing": "browsing"}
        db.get_all_activity_mappings.assert_called_once()

    def test_empty_db(self):
        db = _make_mock_db([])
        mgr = ActivityManager(db)
        assert mgr._cache == {}


class TestNormalizeAndRegister:
    def test_empty_raw_returns_other(self):
        db = _make_mock_db([])
        mgr = ActivityManager(db)

        activity, meta = mgr.normalize_and_register("", "focus")
        assert activity == ""
        assert meta == "other"

    def test_exact_match_returns_existing(self):
        mappings = [{"activity": "programming", "meta_category": "focus", "frame_count": 10}]
        db = _make_mock_db(mappings)
        mgr = ActivityManager(db)

        activity, meta = mgr.normalize_and_register("programming", "focus")
        assert activity == "programming"
        assert meta == "focus"
        db.upsert_activity_mapping.assert_called_once_with("programming", "focus")

    def test_case_insensitive_match(self):
        mappings = [{"activity": "Programming", "meta_category": "focus", "frame_count": 10}]
        db = _make_mock_db(mappings)
        mgr = ActivityManager(db)

        activity, meta = mgr.normalize_and_register("programming", "focus")
        assert activity == "Programming"  # returns the stored form
        assert meta == "focus"

    def test_fuzzy_match_above_threshold(self):
        mappings = [{"activity": "web browsing", "meta_category": "browsing", "frame_count": 10}]
        db = _make_mock_db(mappings)
        mgr = ActivityManager(db)

        # "web browsing" vs "browsing the web" — similarity below 0.7, registers as new
        # Use a closer variant that exceeds threshold
        activity, meta = mgr.normalize_and_register("web-browsing", "browsing")
        # "web-browsing" vs "web browsing" — substring containment 11/12 > 0.7
        assert activity == "web browsing"
        assert meta == "browsing"

    def test_new_activity_registered(self):
        db = _make_mock_db([])
        mgr = ActivityManager(db)

        activity, meta = mgr.normalize_and_register("sleeping", "idle")
        assert activity == "sleeping"
        assert meta == "idle"
        db.upsert_activity_mapping.assert_called_once_with("sleeping", "idle")
        # Verify it was added to cache
        assert mgr._cache["sleeping"] == "idle"

    def test_invalid_meta_defaults_to_other(self):
        db = _make_mock_db([])
        mgr = ActivityManager(db)

        activity, meta = mgr.normalize_and_register("cooking", "invalid_category")
        assert meta == "other"

    def test_empty_meta_defaults_to_other(self):
        db = _make_mock_db([])
        mgr = ActivityManager(db)

        activity, meta = mgr.normalize_and_register("cooking", "")
        assert meta == "other"

    def test_whitespace_stripped(self):
        db = _make_mock_db([])
        mgr = ActivityManager(db)

        activity, meta = mgr.normalize_and_register("  cooking  ", "  break  ")
        assert activity == "cooking"
        assert meta == "break"


class TestGetMetaCategory:
    def test_exact_match(self):
        mappings = [{"activity": "programming", "meta_category": "focus", "frame_count": 10}]
        db = _make_mock_db(mappings)
        mgr = ActivityManager(db)

        assert mgr.get_meta_category("programming") == "focus"

    def test_empty_activity(self):
        db = _make_mock_db([])
        mgr = ActivityManager(db)
        assert mgr.get_meta_category("") == "other"

    def test_normalized_match(self):
        mappings = [{"activity": "Programming", "meta_category": "focus", "frame_count": 10}]
        db = _make_mock_db(mappings)
        mgr = ActivityManager(db)

        assert mgr.get_meta_category("programming") == "focus"

    def test_fuzzy_match(self):
        mappings = [{"activity": "web browsing", "meta_category": "browsing", "frame_count": 10}]
        db = _make_mock_db(mappings)
        mgr = ActivityManager(db)

        # "browsing web" vs "web browsing" has similarity ~0.67, below threshold
        # Use a closer variant: "web browsing!" which contains "web browsing" as substring
        result = mgr.get_meta_category("web browsing!")
        assert result == "browsing"

    def test_no_match_returns_other(self):
        mappings = [{"activity": "programming", "meta_category": "focus", "frame_count": 10}]
        db = _make_mock_db(mappings)
        mgr = ActivityManager(db)

        assert mgr.get_meta_category("xyz_completely_different_9999") == "other"

    def test_none_like_input(self):
        db = _make_mock_db([])
        mgr = ActivityManager(db)
        assert mgr.get_meta_category("") == "other"


class TestGetFrequent:
    def test_returns_activities(self):
        mappings = [
            {"activity": "programming", "meta_category": "focus", "frame_count": 20},
            {"activity": "browsing", "meta_category": "browsing", "frame_count": 10},
        ]
        db = _make_mock_db(mappings)
        mgr = ActivityManager(db)

        result = mgr.get_frequent(limit=5)
        assert result == ["programming", "browsing"]


class TestGetGroupedByMeta:
    def test_groups_by_meta_category(self):
        mappings = [
            {"activity": "programming", "meta_category": "focus", "frame_count": 20},
            {"activity": "coding", "meta_category": "focus", "frame_count": 10},
            {"activity": "browsing", "meta_category": "browsing", "frame_count": 5},
        ]
        db = _make_mock_db(mappings)
        mgr = ActivityManager(db)

        grouped = mgr.get_grouped_by_meta()
        assert "focus" in grouped
        assert grouped["focus"] == ["programming", "coding"]
        assert "browsing" in grouped
        assert grouped["browsing"] == ["browsing"]


class TestValidMetaCategories:
    def test_expected_categories(self):
        expected = {"focus", "communication", "entertainment", "browsing", "break", "idle", "other"}
        assert expected == VALID_META_CATEGORIES
