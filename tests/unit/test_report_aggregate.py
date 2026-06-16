"""JSONL → totals math.

Pins the schema the aggregator recognizes. Unknown keys in records must be
ignored silently; missing keys must default to zero. The report is a
*best-effort* summary — it never crashes on weird data.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scout.report import aggregate


def _write_log(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


class TestAggregate:
    def test_scout_run_record_increments_by_source(self, tmp_path: Path) -> None:
        log = tmp_path / "2026-06-15.jsonl"
        _write_log(log, [{
            "thread_id": "scout-1",
            "agent": "scout",
            "started_at": "2026-06-15T10:00:00+00:00",
            "ended_at": "2026-06-15T10:01:00+00:00",
            "outcome": "ok",
            "summary": "...",
            "stats": {
                "sources_run": [
                    {"source": "hackernews", "queued": 12, "skipped_catalog_dedup": 1},
                    {"source": "lobsters", "queued": 3, "skipped_catalog_dedup": 0},
                ],
                "errors": [],
                "candidates_queued": 15,
                "candidates_skipped_catalog_dedup": 1,
            },
        }])
        t = aggregate([log], period_start=date(2026, 6, 15), period_end=date(2026, 6, 15))
        assert t.runs == 1
        assert t.runs_ok == 1
        assert t.candidates_queued == 15
        assert t.by_source["hackernews"].queued == 12
        assert t.by_source["hackernews"].skipped_catalog == 1
        assert t.by_source["lobsters"].queued == 3

    def test_repo_extraction_warnings_become_triage(self, tmp_path: Path) -> None:
        log = tmp_path / "2026-06-15.jsonl"
        _write_log(log, [{
            "thread_id": "scout-2",
            "agent": "scout",
            "started_at": "2026-06-15T10:00:00+00:00",
            "ended_at": "2026-06-15T10:01:00+00:00",
            "outcome": "partial",
            "summary": "...",
            "stats": {
                "repo_extraction": {
                    "repos_extracted": 1,
                    "children_queued": 0,
                    "warnings": [
                        "container-error: clone-runner exited 128 for "
                        "https://github.com/x/y: fatal: write error: "
                        "No space left on device",
                    ],
                },
            },
        }])
        t = aggregate([log], period_start=date(2026, 6, 15), period_end=date(2026, 6, 15))
        assert t.runs_partial == 1
        assert t.candidates_via_repo_extraction == 0
        assert len(t.triage) == 1
        assert "No space left" in t.triage[0]

    def test_dedup_stats_roll_up(self, tmp_path: Path) -> None:
        log = tmp_path / "2026-06-15.jsonl"
        _write_log(log, [{
            "thread_id": "dedup-1",
            "agent": "scout-dedup",
            "started_at": "2026-06-15T10:00:00+00:00",
            "ended_at": "2026-06-15T10:01:00+00:00",
            "outcome": "ok",
            "summary": "...",
            "stats": {
                "pass1_identity_collapse": 4,
                "pass2_url_canonicalize": 6,
                "pass3_merge_proposals": 2,
                "pass4_auto_archived": 1,
                "rejected_proposals_carried": 0,
            },
        }])
        t = aggregate([log], period_start=date(2026, 6, 15), period_end=date(2026, 6, 15))
        assert t.dedup_identity == 4
        assert t.dedup_url == 6
        assert t.merge_proposals_active == 2
        assert t.auto_archived == 1

    def test_token_burn_fields_are_summed_per_agent_model(self, tmp_path: Path) -> None:
        log = tmp_path / "2026-06-15.jsonl"
        _write_log(log, [
            {
                "thread_id": "rev-1",
                "agent": "scout-reviewer",
                "model": "claude-opus-4-7",
                "started_at": "2026-06-15T10:00:00+00:00",
                "ended_at": "2026-06-15T10:01:00+00:00",
                "outcome": "ok", "summary": "...",
                "input_tokens": 1000, "output_tokens": 50, "tool_calls": 3,
                "cache_read_tokens": 0, "cache_write_tokens": 0,
            },
            {
                "thread_id": "rev-2",
                "agent": "scout-reviewer",
                "model": "claude-opus-4-7",
                "started_at": "2026-06-15T11:00:00+00:00",
                "ended_at": "2026-06-15T11:01:00+00:00",
                "outcome": "ok", "summary": "...",
                "input_tokens": 500, "output_tokens": 30, "tool_calls": 2,
            },
        ])
        t = aggregate([log], period_start=date(2026, 6, 15), period_end=date(2026, 6, 15))
        cell = t.by_token_cell[("scout-reviewer", "claude-opus-4-7")]
        assert cell.input_tokens == 1500
        assert cell.output_tokens == 80
        assert cell.tool_calls == 5
        assert cell.runs_with_tokens == 2

    def test_malformed_lines_are_counted_not_fatal(self, tmp_path: Path) -> None:
        log = tmp_path / "2026-06-15.jsonl"
        log.write_text(
            'not json\n'
            '{"thread_id": "x", "agent": "scout", '
            '"started_at": "2026-06-15T10:00:00+00:00", '
            '"ended_at": "2026-06-15T10:00:01+00:00", '
            '"outcome": "ok", "summary": "ok"}\n'
        )
        t = aggregate([log], period_start=date(2026, 6, 15), period_end=date(2026, 6, 15))
        assert t.records_skipped_malformed == 1
        assert t.runs == 1

    def test_records_outside_window_are_dropped(self, tmp_path: Path) -> None:
        log_in = tmp_path / "2026-06-15.jsonl"
        log_out = tmp_path / "2026-06-01.jsonl"
        rec = {
            "thread_id": "x",
            "agent": "scout",
            "outcome": "ok",
            "summary": "",
        }
        _write_log(log_in, [{**rec, "started_at": "2026-06-15T10:00:00+00:00",
                             "ended_at": "2026-06-15T10:00:01+00:00"}])
        _write_log(log_out, [{**rec, "started_at": "2026-06-01T10:00:00+00:00",
                              "ended_at": "2026-06-01T10:00:01+00:00"}])
        t = aggregate([log_in, log_out],
                       period_start=date(2026, 6, 14),
                       period_end=date(2026, 6, 15))
        assert t.runs == 1
