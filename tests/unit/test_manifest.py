"""Unit tests for the manifest scanner.

Covers the pure functions (parsing, validation, rendering). The end-to-end
`scan()` over the real repo is exercised manually via `uv run manifest`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.manifest import (
    DocumentRecord,
    parse_frontmatter,
    parse_sidecar,
    render_json,
    render_markdown,
    scan,
    validate,
)

# --------------------------------------------------------------------------- #
# parse_frontmatter
# --------------------------------------------------------------------------- #

def test_parse_frontmatter_happy_path(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("---\nname: foo\ntitle: \"Foo\"\nstatus: active\n---\n\n# body\n")
    fm = parse_frontmatter(p)
    assert fm == {"name": "foo", "title": "Foo", "status": "active"}


def test_parse_frontmatter_missing_block_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("# just a heading\n\nno frontmatter here.\n")
    assert parse_frontmatter(p) is None


def test_parse_frontmatter_unterminated_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("---\nname: foo\n# never closes\n")
    assert parse_frontmatter(p) is None


def test_parse_frontmatter_malformed_yaml_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("---\nname: [unclosed\n---\n")
    assert parse_frontmatter(p) is None


def test_parse_frontmatter_empty_block_returns_none(tmp_path: Path) -> None:
    # An empty YAML doc yields None from safe_load, which we treat as missing.
    p = tmp_path / "doc.md"
    p.write_text("---\n---\n")
    assert parse_frontmatter(p) is None


# --------------------------------------------------------------------------- #
# parse_sidecar
# --------------------------------------------------------------------------- #

def test_parse_sidecar_finds_meta_yaml(tmp_path: Path) -> None:
    binary = tmp_path / "deck.pdf"
    binary.write_bytes(b"%PDF-fake")
    sidecar = tmp_path / "deck.pdf.meta.yaml"
    sidecar.write_text("name: deck\ntitle: \"Deck\"\nstatus: active\n")
    fm = parse_sidecar(binary)
    assert fm == {"name": "deck", "title": "Deck", "status": "active"}


def test_parse_sidecar_missing_returns_none(tmp_path: Path) -> None:
    binary = tmp_path / "lonely.png"
    binary.write_bytes(b"\x89PNG")
    assert parse_sidecar(binary) is None


# --------------------------------------------------------------------------- #
# validate
# --------------------------------------------------------------------------- #

def test_validate_missing_frontmatter() -> None:
    assert validate(None) == ["missing-frontmatter"]


def test_validate_flags_missing_required_fields() -> None:
    issues = validate({"name": "x"})
    assert "missing-field:title" in issues
    assert "missing-field:status" in issues
    assert "missing-field:updated_at" in issues
    assert "missing-field:name" not in issues


def test_validate_flags_invalid_status_for_known_kind() -> None:
    issues = validate({
        "name": "x", "title": "X", "kind": "plan",
        "status": "shipped",                    # not in the plan enum
        "updated_at": "2026-06-15",
    })
    assert any(i.startswith("invalid-status:shipped-for-plan") for i in issues)


def test_validate_unknown_kind_skips_status_check() -> None:
    # We don't fail unknown kinds — let them coexist while the convention rolls in.
    issues = validate({
        "name": "x", "title": "X", "kind": "novel-thing",
        "status": "anything", "updated_at": "2026-06-15",
    })
    assert not any(i.startswith("invalid-status:") for i in issues)


def test_validate_accepts_well_formed() -> None:
    issues = validate({
        "name": "x", "title": "X", "kind": "plan",
        "status": "done", "updated_at": "2026-06-15",
    })
    assert issues == []


# --------------------------------------------------------------------------- #
# scan
# --------------------------------------------------------------------------- #

def test_scan_markdown_and_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tools.manifest.REPO_ROOT", tmp_path)

    (tmp_path / "good.md").write_text(
        "---\nname: good\ntitle: Good\nkind: plan\nstatus: done\n"
        "updated_at: 2026-06-15\n---\nbody\n"
    )
    (tmp_path / "bad.md").write_text("# no frontmatter\n")

    binary = tmp_path / "deck.pdf"
    binary.write_bytes(b"%PDF")
    (tmp_path / "deck.pdf.meta.yaml").write_text(
        "name: deck\ntitle: Deck\nkind: generated\nstatus: active\n"
        "updated_at: 2026-06-15\n"
    )

    (tmp_path / "ignored.py").write_text("x = 1\n")            # not a document
    (tmp_path / "config.yaml").write_text("a: 1\n")            # not a document

    records = scan(files=[
        tmp_path / "good.md",
        tmp_path / "bad.md",
        tmp_path / "deck.pdf",
        tmp_path / "deck.pdf.meta.yaml",                       # excluded
        tmp_path / "ignored.py",
        tmp_path / "config.yaml",
    ])

    paths = {r.path: r for r in records}
    assert set(paths) == {"good.md", "bad.md", "deck.pdf"}

    assert paths["good.md"].issues == []
    assert paths["good.md"].fm_source == "inline"

    assert paths["bad.md"].issues == ["missing-frontmatter"]

    assert paths["deck.pdf"].fm_source == "sidecar"
    assert paths["deck.pdf"].issues == []


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

def test_render_markdown_includes_summary_and_table() -> None:
    records = [
        DocumentRecord(
            path="a.md", fm_source="inline",
            kind="plan", name="a", title="A",
            status="done", updated_at="2026-06-15",
            has_frontmatter=True,
        ),
        DocumentRecord(
            path="b.md", fm_source="missing",
            has_frontmatter=False, issues=["missing-frontmatter"],
        ),
    ]
    out = render_markdown(records)
    assert "name: manifest" in out
    assert "kind: generated" in out
    assert "Documents scanned: **2**" in out
    assert "Missing frontmatter / sidecar: **1**" in out
    assert "| `a.md` | `plan` | `a` | A | `done` | 2026-06-15 |  |" in out
    assert "missing-frontmatter" in out


def test_render_markdown_pipe_in_title_is_escaped() -> None:
    records = [DocumentRecord(
        path="a.md", fm_source="inline", kind="plan", name="a",
        title="Has | pipe", status="done", updated_at="2026-06-15",
        has_frontmatter=True,
    )]
    out = render_markdown(records)
    assert "Has \\| pipe" in out


def test_render_json_is_valid_json() -> None:
    import json as _json

    records = [DocumentRecord(path="a.md", has_frontmatter=False, issues=["missing-frontmatter"])]
    parsed = _json.loads(render_json(records))
    assert parsed[0]["path"] == "a.md"
    assert parsed[0]["issues"] == ["missing-frontmatter"]
