"""End-to-end: fixture JSONLs → rendered markdown; second --write is a no-op.

Idempotency contract from Phase 7's session prompt: rendering the same
inputs twice must produce byte-identical output, so `scout report --write`
can be re-run without dirtying git.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scout.report import aggregate, render


def _write_log(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def test_aggregate_then_render_is_byte_identical_on_second_pass(
    tmp_path: Path,
) -> None:
    threads = tmp_path / "threads"
    threads.mkdir()
    _write_log(threads / "2026-06-14.jsonl", [
        {
            "thread_id": "scout-a",
            "agent": "scout",
            "started_at": "2026-06-14T10:00:00+00:00",
            "ended_at": "2026-06-14T10:01:00+00:00",
            "outcome": "ok",
            "summary": "queued=5",
            "stats": {
                "sources_run": [{"source": "hackernews", "queued": 5, "skipped_catalog_dedup": 0}],
                "errors": [],
                "candidates_queued": 5,
            },
        },
    ])
    _write_log(threads / "2026-06-15.jsonl", [
        {
            "thread_id": "dedup-a",
            "agent": "scout-dedup",
            "started_at": "2026-06-15T10:00:00+00:00",
            "ended_at": "2026-06-15T10:00:30+00:00",
            "outcome": "ok",
            "summary": "identity=2 url=0",
            "stats": {
                "pass1_identity_collapse": 2,
                "pass2_url_canonicalize": 0,
                "pass3_merge_proposals": 1,
                "pass4_auto_archived": 0,
                "rejected_proposals_carried": 0,
            },
        },
    ])

    logs = sorted(threads.glob("*.jsonl"))
    totals_a = aggregate(logs, period_start=date(2026, 6, 14), period_end=date(2026, 6, 15))
    md_a = render(totals_a)
    totals_b = aggregate(logs, period_start=date(2026, 6, 14), period_end=date(2026, 6, 15))
    md_b = render(totals_b)

    assert md_a == md_b

    # Sanity: the rollup picked up the meaningful events.
    assert "Runs: 2" in md_a
    assert "5" in md_a  # candidates queued
    assert "Identity / URL collapses by dedup: 2" in md_a
    assert "1 active" in md_a  # merge proposals

    # Write twice; second write doesn't change bytes.
    reports = tmp_path / "reports"
    reports.mkdir()
    out = reports / "2026-06-14-week.md"
    out.write_text(md_a)
    first = out.read_bytes()
    out.write_text(render(aggregate(
        logs, period_start=date(2026, 6, 14), period_end=date(2026, 6, 15),
    )))
    assert out.read_bytes() == first


def test_empty_window_renders_no_data_notice(tmp_path: Path) -> None:
    totals = aggregate([], period_start=date(2026, 6, 15), period_end=date(2026, 6, 15))
    md = render(totals)
    assert "_No thread-log records in this window._" in md
