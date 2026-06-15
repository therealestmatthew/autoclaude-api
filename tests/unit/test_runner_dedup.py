"""Test runner's catalog-URL dedup behavior.

Uses a tmp_path catalog dir + monkeypatches the runner's CATALOG_DIR.
"""

from __future__ import annotations

import textwrap

import pytest

from scout.agent import runner


@pytest.fixture
def fake_catalog(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    # An entry whose source.url + alternates should both end up in the set.
    (catalog / "foo.md").write_text(textwrap.dedent("""\
        ---
        name: foo
        kind: repo
        title: Foo
        status: reviewed
        source:
          type: github
          url: https://github.com/alice/foo
          alternates:
            - type: github
              url: https://github.com/anthropics/marketplace
        discovered:
          via: manual
          on: 2026-06-14
        created_at: 2026-06-14
        updated_at: 2026-06-14
        ---
        body
    """))
    # An entry whose source URL is a sub-tree — canonical form must also dedup.
    (catalog / "bar.md").write_text(textwrap.dedent("""\
        ---
        name: bar
        kind: skill
        title: Bar
        status: reviewed
        source:
          type: github
          url: https://github.com/bob/bar/tree/main/skills/bar
        discovered:
          via: manual
          on: 2026-06-14
        created_at: 2026-06-14
        updated_at: 2026-06-14
        ---
    """))
    # A malformed file — must not crash the collector.
    (catalog / "broken.md").write_text("not frontmatter at all\n")

    monkeypatch.setattr(runner, "CATALOG_DIR", catalog)
    return catalog


def test_collects_primary_and_alternate_urls(fake_catalog):
    urls = runner._existing_catalog_urls()
    assert "https://github.com/alice/foo" in urls
    assert "https://github.com/anthropics/marketplace" in urls


def test_collects_canonical_form_for_subtree_urls(fake_catalog):
    urls = runner._existing_catalog_urls()
    assert "https://github.com/bob/bar/tree/main/skills/bar" in urls
    # The canonical form is also in the set, so future candidates pointing at
    # the repo root would dedup against it.
    assert "https://github.com/bob/bar" in urls


def test_malformed_file_does_not_crash(fake_catalog):
    # Just calling it returned without raising is the assertion.
    runner._existing_catalog_urls()
