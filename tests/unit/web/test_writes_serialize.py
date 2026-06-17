"""Round-trip tests for the markdown serialiser."""

from __future__ import annotations

from web.apps.api.writes.serialize import (
    parse_body,
    parse_frontmatter,
    render_document,
    replace_body,
    replace_frontmatter,
    split_document,
)

SAMPLE = """---
name: alpha-tool
kind: repo
title: Alpha tool
tags:
- foo
- bar
status: reviewed
---

# alpha-tool

A fixture catalog asset.
"""


def test_split_document() -> None:
    fm, body = split_document(SAMPLE)
    assert "name: alpha-tool" in fm
    assert body.startswith("# alpha-tool")


def test_parse_frontmatter() -> None:
    fm = parse_frontmatter(SAMPLE)
    assert fm["name"] == "alpha-tool"
    assert fm["tags"] == ["foo", "bar"]


def test_parse_body() -> None:
    body = parse_body(SAMPLE)
    assert body.startswith("# alpha-tool")


def test_render_document_round_trip() -> None:
    fm = parse_frontmatter(SAMPLE)
    body = parse_body(SAMPLE)
    rendered = render_document(fm, body)
    re_fm = parse_frontmatter(rendered)
    re_body = parse_body(rendered)
    assert re_fm == fm
    assert re_body.strip() == body.strip()


def test_replace_frontmatter_preserves_body() -> None:
    out = replace_frontmatter(SAMPLE, {"name": "renamed", "kind": "skill", "title": "x"})
    assert "renamed" in out
    assert "# alpha-tool" in out


def test_replace_body_preserves_frontmatter() -> None:
    out = replace_body(SAMPLE, "# new body\n")
    assert "name: alpha-tool" in out
    assert "# new body" in out
    assert "fixture catalog asset" not in out


def test_render_does_not_wrap_long_urls() -> None:
    long_url = "https://example.com/" + "x" * 200
    fm = {"name": "x", "kind": "article", "source": {"url": long_url}}
    rendered = render_document(fm, "")
    assert long_url in rendered  # not broken across lines
