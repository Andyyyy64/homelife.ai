"""Tests for daemon.analyzer — FrameAnalyzer._parse_analysis() static method."""

from __future__ import annotations

import json

from daemon.analyzer import FrameAnalyzer


class TestParseAnalysisJSON:
    """Test parsing well-formed JSON responses."""

    def test_valid_json(self):
        raw = json.dumps({
            "activity": "programming",
            "meta_category": "focus",
            "description": "User is writing code",
        })
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)

        assert desc == "User is writing code"
        assert activity == "programming"
        assert meta == "focus"

    def test_json_with_markdown_code_block(self):
        raw = '```json\n{"activity": "browsing", "meta_category": "browsing", "description": "Browsing the web"}\n```'
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)

        assert desc == "Browsing the web"
        assert activity == "browsing"
        assert meta == "browsing"

    def test_json_with_plain_code_block(self):
        raw = '```\n{"activity": "reading", "meta_category": "focus", "description": "Reading docs"}\n```'
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)

        assert desc == "Reading docs"
        assert activity == "reading"
        assert meta == "focus"

    def test_json_embedded_in_text(self):
        raw = 'Here is my analysis:\n{"activity": "coding", "meta_category": "focus", "description": "Coding in VS Code"}\nEnd.'
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)

        assert desc == "Coding in VS Code"
        assert activity == "coding"
        assert meta == "focus"

    def test_missing_meta_category_defaults_to_other(self):
        raw = json.dumps({
            "activity": "sleeping",
            "description": "Person is sleeping",
        })
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)

        assert activity == "sleeping"
        assert meta == "other"

    def test_missing_description(self):
        raw = json.dumps({
            "activity": "idle",
            "meta_category": "idle",
        })
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)

        assert desc == ""
        assert activity == "idle"
        assert meta == "idle"

    def test_empty_json_object(self):
        raw = "{}"
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)

        assert desc == ""
        assert activity == ""
        assert meta == "other"

    def test_japanese_content(self):
        raw = json.dumps({
            "activity": "プログラミング",
            "meta_category": "focus",
            "description": "ユーザーはVS Codeでコードを書いている",
        }, ensure_ascii=False)
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)

        assert activity == "プログラミング"
        assert desc == "ユーザーはVS Codeでコードを書いている"
        assert meta == "focus"


class TestParseAnalysisFallback:
    """Test fallback behavior when parsing fails."""

    def test_empty_string(self):
        desc, activity, meta = FrameAnalyzer._parse_analysis("")
        assert desc == ""
        assert activity == ""
        assert meta == "other"

    def test_whitespace_only(self):
        desc, activity, meta = FrameAnalyzer._parse_analysis("   \n  ")
        assert desc == ""
        assert activity == ""
        assert meta == "other"

    def test_plain_text_fallback(self):
        raw = "The person is sitting at a desk working on a computer."
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)

        # Should use the entire text as description
        assert desc == raw
        assert activity == ""
        assert meta == "other"

    def test_malformed_json(self):
        raw = '{"activity": "coding", "description": broken}'
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)

        # Falls back to raw text since JSON parsing fails
        assert desc == raw
        assert activity == ""
        assert meta == "other"

    def test_json_with_trailing_text(self):
        raw = '{"activity": "reading", "meta_category": "focus", "description": "Reading a book"} some extra text'
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)

        # The embedded JSON extraction ({...}) should still work
        assert activity == "reading"
        assert meta == "focus"
        assert desc == "Reading a book"

    def test_multiple_json_objects_uses_outermost(self):
        # rfind("}") finds the last }, so it grabs the full range
        raw = '{"activity": "a", "description": "first"} {"activity": "b", "description": "second"}'
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)
        # The first json.loads(raw) will fail, then it tries raw[start:end]
        # where start=0 (first {) and end = last } + 1, which covers both objects -> invalid JSON
        # So it falls back to raw text
        assert desc == raw
        assert activity == ""
        assert meta == "other"

    def test_code_block_with_extra_text_inside(self):
        raw = '```json\n{"activity": "gaming", "meta_category": "entertainment", "description": "Playing a game"}\n```\nAdditional notes here.'
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)

        assert activity == "gaming"
        assert meta == "entertainment"
        assert desc == "Playing a game"


class TestParseAnalysisEdgeCases:
    """Edge cases for _parse_analysis."""

    def test_nested_code_blocks(self):
        raw = '```\n```\n{"activity": "test", "description": "nested", "meta_category": "other"}\n```\n```'
        # The toggle logic: first ``` -> in_block=True, second ``` -> in_block=False,
        # third ``` -> in_block=True (captures JSON line), fourth ``` -> in_block=False
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)
        assert activity == "test"
        assert desc == "nested"

    def test_json_with_unicode_escape(self):
        raw = '{"activity": "\\u30d7\\u30ed\\u30b0\\u30e9\\u30df\\u30f3\\u30b0", "meta_category": "focus", "description": "coding"}'
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)
        assert activity == "プログラミング"
        assert meta == "focus"

    def test_json_with_newlines_in_description(self):
        raw = json.dumps({
            "activity": "reading",
            "meta_category": "focus",
            "description": "Line 1\nLine 2",
        })
        desc, activity, meta = FrameAnalyzer._parse_analysis(raw)
        assert "Line 1" in desc
        assert "Line 2" in desc
