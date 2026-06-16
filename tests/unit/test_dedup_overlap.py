"""Unit tests for scout.dedup.overlap: title tokens, Jaccard, author norm."""

from __future__ import annotations

import pytest

from scout.dedup.overlap import jaccard, primary_author, title_tokens


class TestTitleTokens:
    def test_lowercases_and_splits(self) -> None:
        assert title_tokens("Claude Code Best Practices") == {
            "claude", "code", "best", "practices",
        }

    def test_strips_stopwords(self) -> None:
        # "to", "the", "of" should disappear.
        assert title_tokens("Guide to the History of MCP") == {
            "guide", "history", "mcp",
        }

    def test_strips_single_character_tokens(self) -> None:
        # "a" is a stopword but "x" isn't — both should drop because we
        # require len > 1.
        assert title_tokens("X a Y Tool") == {"tool"}

    def test_empty_string_returns_empty(self) -> None:
        assert title_tokens("") == set()
        assert title_tokens(None) == set()  # type: ignore[arg-type]

    def test_punctuation_is_irrelevant(self) -> None:
        assert title_tokens("foo-bar: a baz!") == {"foo", "bar", "baz"}


class TestJaccard:
    def test_full_overlap_is_one(self) -> None:
        a = {"x", "y", "z"}
        assert jaccard(a, a) == pytest.approx(1.0)

    def test_no_overlap_is_zero(self) -> None:
        assert jaccard({"a", "b"}, {"c", "d"}) == pytest.approx(0.0)

    def test_half_overlap(self) -> None:
        # {a,b} ∩ {b,c} = {b}; ∪ = {a,b,c}. Jaccard = 1/3.
        assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)

    def test_both_empty_is_zero_not_undefined(self) -> None:
        assert jaccard(set(), set()) == 0.0


class TestPrimaryAuthor:
    def test_first_author_lowercased(self) -> None:
        assert primary_author(["Anthropic", "alice"]) == "anthropic"

    def test_empty_input(self) -> None:
        assert primary_author(None) == ""
        assert primary_author([]) == ""

    def test_strips_whitespace(self) -> None:
        assert primary_author(["  Alice  "]) == "alice"
