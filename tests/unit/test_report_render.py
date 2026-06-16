"""Totals → markdown rendering.

A snapshot of the rollup shape. Determinism is the contract: the same
Totals must produce byte-identical markdown so `scout report --write` can
be re-run without dirtying git.
"""

from __future__ import annotations

from datetime import date

from scout.report import render
from scout.report.aggregate import AgentTotals, SourceTotals, TokenTotals, Totals


def _populated_totals() -> Totals:
    t = Totals(period_start=date(2026, 6, 8), period_end=date(2026, 6, 14))
    t.runs = 14
    t.runs_ok = 12
    t.runs_partial = 2
    t.candidates_queued = 412
    t.candidates_via_repo_extraction = 287
    t.dedup_identity = 12
    t.dedup_url = 26
    t.merge_proposals_active = 11
    t.merge_proposals_carried = 3
    t.auto_archived = 2
    t.by_agent = {
        "scout": AgentTotals(runs=7, ok=6, partial=1, errors=0, notable=["reddit 403"]),
        "scout-dedup": AgentTotals(runs=2, ok=2, partial=0, errors=0),
        "scout-extract-repo": AgentTotals(runs=5, ok=3, partial=2, errors=0),
    }
    t.by_source = {
        "hackernews": SourceTotals(queued=382, skipped_catalog=0, errors=0),
        "awesome-lists": SourceTotals(queued=27, skipped_catalog=0, errors=0),
    }
    t.triage = ["No space left on device on clone-runner"]
    return t


class TestRender:
    def test_empty_window_emits_no_data_notice(self) -> None:
        t = Totals(period_start=date(2026, 6, 15), period_end=date(2026, 6, 15))
        md = render(t)
        assert "# Scout health report" in md
        assert "_No thread-log records in this window._" in md

    def test_populated_totals_render_all_sections(self) -> None:
        md = render(_populated_totals())
        assert "Scout health report — 2026-06-08 → 2026-06-14" in md
        assert "Runs: 14 (12 ok, 2 partial)" in md
        assert "Candidates queued: 412" in md
        assert "287 via repo extraction" in md
        assert "## By agent" in md
        assert "| scout | 7 | 6 | 1 | 0 | reddit 403 |" in md
        assert "## By source" in md
        assert "| hackernews | 382 | 0 | 0 |" in md
        assert "## Token burn" in md
        assert "reviewer / curator agents land in Phase 8+" in md
        assert "No space left on device" in md

    def test_render_is_deterministic(self) -> None:
        t1 = _populated_totals()
        t2 = _populated_totals()
        assert render(t1) == render(t2)

    def test_token_burn_cells_are_rendered_when_present(self) -> None:
        t = Totals(period_start=date(2026, 6, 15), period_end=date(2026, 6, 15))
        t.runs = 1
        t.runs_ok = 1
        t.by_agent = {"scout-reviewer": AgentTotals(runs=1, ok=1)}
        t.by_token_cell = {
            ("scout-reviewer", "claude-opus-4-7"): TokenTotals(
                input_tokens=1500, output_tokens=80, tool_calls=5,
                runs_with_tokens=2,
            ),
        }
        md = render(t)
        assert "| scout-reviewer | claude-opus-4-7 | 2 | 1500 | 80 | 0/0 | 5 |" in md
        # Don't show the "no LLM agents" placeholder when we have data.
        assert "reviewer / curator agents land in Phase 8+" not in md
