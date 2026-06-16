"""Doctor catalog-integrity checks.

The reviewer reads doctor output to decide what to look at. These tests
pin the failure modes that matter: silent orphans, broken supersedes,
slug/filename drift, and stale-reviewed informational signal.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from scout.doctor import run_checks

VALID_FRONTMATTER = """---
name: {name}
kind: repo
title: "{name}"
status: {status}
source:
  type: github
  url: https://github.com/x/{name}
  authors: []
  license: ""
discovered:
  via: manual
  on: 2026-06-01
created_at: 2026-06-01
updated_at: {updated}
{extra}
---
body
"""


def _write_asset(
    catalog_dir: Path,
    *,
    name: str,
    filename: str | None = None,
    status: str = "reviewed",
    updated: str = "2026-06-15",
    extra: str = "",
) -> Path:
    catalog_dir.mkdir(parents=True, exist_ok=True)
    path = catalog_dir / f"{filename or name}.md"
    path.write_text(VALID_FRONTMATTER.format(
        name=name, status=status, updated=updated, extra=extra,
    ))
    return path


class TestDoctor:
    def test_clean_catalog_has_no_findings(self, tmp_path: Path) -> None:
        catalog = tmp_path / "catalog"
        _write_asset(catalog, name="alpha")
        _write_asset(catalog, name="beta")
        report = run_checks(catalog, today=date(2026, 6, 15))
        assert report.by_kind() == {}

    def test_orphan_child_is_reported(self, tmp_path: Path) -> None:
        catalog = tmp_path / "catalog"
        _write_asset(catalog, name="child",
                     extra="relations:\n  parent: missing-parent")
        report = run_checks(catalog, today=date(2026, 6, 15))
        kinds = report.by_kind()
        assert kinds.get("orphan-child") == 1
        assert any("missing-parent" in f.detail for f in report.findings
                   if f.kind == "orphan-child")

    def test_parent_resolved_via_queue_not_orphan(self, tmp_path: Path) -> None:
        catalog = tmp_path / "catalog"
        queue = tmp_path / "queue"
        _write_asset(catalog, name="child",
                     extra="relations:\n  parent: parent-in-queue")
        queue.mkdir()
        (queue / "anything.md").write_text(VALID_FRONTMATTER.format(
            name="parent-in-queue", status="draft",
            updated="2026-06-15", extra="",
        ))
        report = run_checks(catalog, queue, today=date(2026, 6, 15))
        assert report.by_kind().get("orphan-child", 0) == 0

    def test_broken_supersedes(self, tmp_path: Path) -> None:
        catalog = tmp_path / "catalog"
        _write_asset(catalog, name="alpha",
                     extra="relations:\n  supersedes: [ghost]")
        report = run_checks(catalog, today=date(2026, 6, 15))
        assert report.by_kind().get("broken-supersedes") == 1

    def test_slug_mismatch_reported_and_fixed(self, tmp_path: Path) -> None:
        catalog = tmp_path / "catalog"
        _write_asset(catalog, name="real-name", filename="wrong-name")
        report = run_checks(catalog, today=date(2026, 6, 15), fix=True)
        assert report.by_kind().get("slug-mismatch") == 1
        assert (catalog / "real-name.md").exists()
        assert not (catalog / "wrong-name.md").exists()
        assert any("real-name" in fx for fx in report.fixes_applied)

    def test_missing_required_field(self, tmp_path: Path) -> None:
        catalog = tmp_path / "catalog"
        # No `created_at:` line at all.
        (catalog).mkdir()
        (catalog / "bad.md").write_text(
            "---\n"
            "name: bad\n"
            "kind: repo\n"
            "title: bad\n"
            "status: draft\n"
            "source: {type: github, url: https://github.com/x/bad}\n"
            "discovered: {via: manual, on: 2026-06-01}\n"
            "updated_at: 2026-06-15\n"
            "---\nbody\n"
        )
        report = run_checks(catalog, today=date(2026, 6, 15))
        assert any(
            f.kind == "missing-required-field" and "created_at" in f.detail
            for f in report.findings
        )

    def test_stale_reviewed_informational(self, tmp_path: Path) -> None:
        catalog = tmp_path / "catalog"
        _write_asset(
            catalog, name="old", status="reviewed", updated="2026-04-01",
        )
        report = run_checks(catalog, today=date(2026, 6, 15))
        assert report.by_kind().get("stale-reviewed") == 1
