"""JSONL thread logs → totals.

Pure function. Takes a list of JSONL files (or the directory) plus a date
window and returns a `Totals` dataclass the renderer can consume. No I/O
beyond reading the files.

The schema accepted from each record is intentionally permissive: any
top-level keys not listed below are ignored. Records that fail to parse
are counted but otherwise dropped — bad data should never crash the rollup.

Recognized record keys:

- `thread_id`     — string id (informational)
- `agent`         — string ("scout" | "scout-extract-repo" | "scout-dedup" | …)
- `outcome`       — "ok" | "partial" | "error" (others bucket to "error")
- `started_at`    — ISO timestamp; we use the date portion to bucket
- `summary`       — short text echoed in the report
- `stats`         — agent-specific nested dict; the keys we look at:
    * `sources_run[].source` / `.queued` / `.skipped_catalog_dedup`
    * `errors[]`
    * `repo_extraction.repos_extracted` / `.children_queued` / `.warnings`
    * `pass3_merge_proposals` / `pass4_auto_archived` / `rejected_proposals_carried`

Token-burn fields (forward-looking):

- `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`,
  `tool_calls`, `model` — when present, summed per `(agent, model)` cell.
  No emitter writes these yet (reviewer/curator agents land Phase 8+); the
  rollup recognizes them now so when they appear no further code changes.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


@dataclass
class AgentTotals:
    runs: int = 0
    ok: int = 0
    partial: int = 0
    errors: int = 0
    notable: list[str] = field(default_factory=list)


@dataclass
class SourceTotals:
    queued: int = 0
    skipped_catalog: int = 0
    errors: int = 0


@dataclass
class TokenTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    tool_calls: int = 0
    runs_with_tokens: int = 0


@dataclass
class Totals:
    period_start: date
    period_end: date
    records_seen: int = 0
    records_skipped_malformed: int = 0
    runs: int = 0
    runs_ok: int = 0
    runs_partial: int = 0
    candidates_queued: int = 0
    candidates_via_repo_extraction: int = 0
    dedup_identity: int = 0
    dedup_url: int = 0
    merge_proposals_active: int = 0
    merge_proposals_carried: int = 0
    auto_archived: int = 0
    by_agent: dict[str, AgentTotals] = field(default_factory=dict)
    by_source: dict[str, SourceTotals] = field(default_factory=dict)
    by_token_cell: dict[tuple[str, str], TokenTotals] = field(default_factory=dict)
    triage: list[str] = field(default_factory=list)


def aggregate(
    log_paths: Iterable[Path],
    *,
    period_start: date,
    period_end: date,
) -> Totals:
    """Read `log_paths` and accumulate everything inside the inclusive
    `[period_start, period_end]` window. Files outside the window are
    skipped at the file level; records outside the window are dropped
    individually."""
    totals = Totals(period_start=period_start, period_end=period_end)
    seen_triage: set[str] = set()

    for path in log_paths:
        # Daily file is named YYYY-MM-DD.jsonl. If we can parse the stem
        # as a date we can short-circuit files outside the window.
        try:
            file_d = date.fromisoformat(path.stem)
        except ValueError:
            file_d = None
        if file_d is not None and (file_d < period_start or file_d > period_end):
            continue

        try:
            text = path.read_text()
        except OSError:
            continue

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            totals.records_seen += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                totals.records_skipped_malformed += 1
                continue
            if not isinstance(rec, dict):
                totals.records_skipped_malformed += 1
                continue

            rec_d = _record_date(rec)
            if rec_d is not None and (rec_d < period_start or rec_d > period_end):
                continue

            _absorb(rec, totals, seen_triage=seen_triage)

    return totals


def _record_date(rec: dict[str, Any]) -> date | None:
    started = rec.get("started_at")
    if isinstance(started, str):
        # Tolerate Z-suffixed timestamps as well as +00:00.
        s = started.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s).date()
        except ValueError:
            return None
    return None


def _absorb(rec: dict[str, Any], t: Totals, *, seen_triage: set[str]) -> None:
    agent = str(rec.get("agent") or "unknown")
    outcome = str(rec.get("outcome") or "unknown")

    bucket = t.by_agent.setdefault(agent, AgentTotals())
    bucket.runs += 1
    t.runs += 1
    if outcome == "ok":
        bucket.ok += 1
        t.runs_ok += 1
    elif outcome == "partial":
        bucket.partial += 1
        t.runs_partial += 1
    else:
        bucket.errors += 1

    stats = rec.get("stats") if isinstance(rec.get("stats"), dict) else {}

    # Scout-style per-source breakdown.
    for sr in stats.get("sources_run") or []:
        if not isinstance(sr, dict):
            continue
        source = str(sr.get("source") or "unknown")
        s = t.by_source.setdefault(source, SourceTotals())
        s.queued += _safe_int(sr.get("queued"))
        s.skipped_catalog += _safe_int(sr.get("skipped_catalog_dedup"))
        t.candidates_queued += _safe_int(sr.get("queued"))

    for e in stats.get("errors") or []:
        # Errors can be dicts ({"source": ..., "error": ...}) or strings.
        source = None
        msg = None
        if isinstance(e, dict):
            source = e.get("source")
            msg = e.get("error")
        elif isinstance(e, str):
            msg = e
        if isinstance(source, str):
            t.by_source.setdefault(source, SourceTotals()).errors += 1
        if isinstance(msg, str) and msg not in bucket.notable:
            bucket.notable.append(msg[:120])

    # Repo extraction nested totals (emitted by scout's tail step).
    repo_ext = stats.get("repo_extraction")
    if isinstance(repo_ext, dict):
        t.candidates_via_repo_extraction += _safe_int(repo_ext.get("children_queued"))
        for w in repo_ext.get("warnings") or []:
            if isinstance(w, str):
                short = w.splitlines()[0][:200] if w else ""
                if short and short not in seen_triage:
                    seen_triage.add(short)
                    t.triage.append(short)

    # Extract-repo-agent record top-level warnings.
    if agent == "scout-extract-repo":
        for w in stats.get("warnings") or []:
            if isinstance(w, str):
                short = w.splitlines()[0][:200] if w else ""
                if short and short not in seen_triage:
                    seen_triage.add(short)
                    t.triage.append(short)

    # Dedup stats: pass1..pass4 + proposals.
    t.dedup_identity += _safe_int(stats.get("pass1_identity_collapse"))
    t.dedup_url += _safe_int(stats.get("pass2_url_canonicalize"))
    t.merge_proposals_active += _safe_int(stats.get("pass3_merge_proposals"))
    t.auto_archived += _safe_int(stats.get("pass4_auto_archived"))
    t.merge_proposals_carried += _safe_int(stats.get("rejected_proposals_carried"))

    # Token-burn fields (optional; live on the top-level record).
    if any(
        k in rec for k in
        ("input_tokens", "output_tokens", "cache_read_tokens",
         "cache_write_tokens", "tool_calls")
    ):
        model = str(rec.get("model") or "unknown")
        cell = t.by_token_cell.setdefault((agent, model), TokenTotals())
        cell.input_tokens += _safe_int(rec.get("input_tokens"))
        cell.output_tokens += _safe_int(rec.get("output_tokens"))
        cell.cache_read_tokens += _safe_int(rec.get("cache_read_tokens"))
        cell.cache_write_tokens += _safe_int(rec.get("cache_write_tokens"))
        cell.tool_calls += _safe_int(rec.get("tool_calls"))
        cell.runs_with_tokens += 1


def _safe_int(v: object) -> int:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0
