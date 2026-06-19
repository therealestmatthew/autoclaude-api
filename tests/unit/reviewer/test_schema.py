"""Tests for scout/reviewer/schema.py — Decision validation."""

import pytest
from pydantic import ValidationError

from scout.reviewer.schema import EMIT_DECISION_TOOL, Decision


class TestDecision:
    def test_basic_keep(self):
        d = Decision(action="keep", confidence=0.9, rationale="High value repo.")
        assert d.action == "keep"
        assert d.scope == "self"
        assert d.target_slug is None

    def test_basic_discard(self):
        d = Decision(action="discard", confidence=0.95, rationale="Transient news.")
        assert d.action == "discard"

    def test_merge_requires_target_slug(self):
        with pytest.raises((ValidationError, ValueError)):
            Decision(action="merge", confidence=0.8, rationale="Duplicate.")

    def test_merge_with_target_slug(self):
        d = Decision(
            action="merge",
            target_slug="anthropic",
            confidence=0.85,
            rationale="Same org, different source.",
        )
        assert d.target_slug == "anthropic"

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            Decision(action="keep", confidence=1.5, rationale="x")
        with pytest.raises(ValidationError):
            Decision(action="keep", confidence=-0.1, rationale="x")

    def test_suggested_slug(self):
        d = Decision(
            action="keep",
            confidence=0.9,
            rationale="Good content.",
            suggested_slug="governor",
        )
        assert d.suggested_slug == "governor"

    def test_parent_with_children_scope(self):
        d = Decision(
            action="keep",
            confidence=0.85,
            rationale="Parent keep.",
            scope="parent-with-children",
        )
        assert d.scope == "parent-with-children"

    def test_flags(self):
        d = Decision(
            action="keep",
            confidence=0.7,
            rationale="Subdirectory URL.",
            flags={"url_target": "subdir", "author_mismatch": True},
        )
        assert d.flags["url_target"] == "subdir"

    def test_suggested_edits(self):
        d = Decision(
            action="keep",
            confidence=0.8,
            rationale="Good repo.",
            suggested_edits={"tags": ["aws", "bedrock"]},
        )
        assert d.suggested_edits["tags"] == ["aws", "bedrock"]


class TestEmitDecisionTool:
    def test_tool_has_required_fields(self):
        schema = EMIT_DECISION_TOOL["input_schema"]
        required = schema.get("required", [])
        assert "action" in required
        assert "confidence" in required
        assert "rationale" in required

    def test_action_enum(self):
        schema = EMIT_DECISION_TOOL["input_schema"]
        enum = schema["properties"]["action"]["enum"]
        assert set(enum) == {"keep", "merge", "discard"}
