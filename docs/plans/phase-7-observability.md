---
name: phase-7-observability
title: "Phase 7 — Command-center observability"
phase: 7
status: draft
created_at: 2026-06-15
updated_at: 2026-06-15
completed_at:
supersedes: []
superseded_by:
locked_decisions:
  - "Markdown-first. Rollup reports are markdown committed to /command-center/token-burn/reports/ (or a sibling). No DB, no Grafana. Set in Phase 0."
  - "Thread logs are append-only JSONL at /command-center/threads/<date>.jsonl. Already in use by scout / scout-dedup / scout-extract-repo. Set in Phase 2."
  - "Operator-pull, not push. Phase 7 ships CLI commands an operator runs; no Slack / email / pager integration. Set here (deferred to later)."
  - "Token-burn schema lands NOW even though no LLM-driven agent emits tokens yet — the plumbing exists so reviewer/curator agents (Phase 8+) just emit and the rollup picks them up. Set here."
---

# Phase 7 — Command-center observability

## Goal

Turn the existing append-only thread log into something an operator can
actually act on: daily and weekly rollups of what the system did, what
broke, and (once LLM-driven agents land) what it cost. Close the Phase 6
URL-liveness loop so pass 4 of the dedup engine starts firing on real
catalog rot.

Output of the phase: an operator who runs `uv run scout report` once a
week can answer "is the system healthy, what failed, what got added to
the queue, what got reviewed into the catalog, how many tokens did the
reviewer agent burn" without grepping JSONL by hand.

## Non-goals (out of scope for this phase)

- **A reviewer agent.** Phase 7 builds the observability *around* future
  agents; building the agents themselves is Phase 8+.
- **Real-time dashboards.** Grafana, web UIs, anything served. This stays
  markdown-first; reports are files you read, not pages you load.
- **Push notifications.** Slack, email, pager. Operator-pull only in v1.
- **Distributed tracing across machines.** Single-machine operation is
  the scope; thread logs are per-machine and don't merge.
- **Anomaly detection / ML.** A threshold-based "errors > N this week"
  view is enough; smarter analysis is later.

## Constraints (inherited)

- **Markdown-first, no DB.** Rollups are markdown. Raw logs stay JSONL.
- **Gitignored raw data, committed rollups.** `*.jsonl` and `*.log` under
  `/command-center/` are gitignored; rollup *reports* land in a tracked
  `reports/` subdir.
- **Determinism.** A rollup over the same input dates produces the same
  output. No timestamps in the body unless they're inputs.
- **No bare XML / sanitization rules** still apply if rollups ever fetch
  external content. For Phase 7 they don't — only local files.

## Design

### 1. URL liveness checker

A standalone command that HEADs every `/catalog/` asset's `source.url`,
records the result in `/scout/state/url-liveness.json`, and feeds pass 4
of the dedup engine.

```sh
uv run scout check-urls          # check every catalog source.url
uv run scout check-urls -v
uv run scout check-urls --since 2026-06-01    # only re-check entries last touched before this
```

State shape (matches what the dedup engine already reads):

```json
{
  "checks": {
    "<url>": {
      "404_count": 3,
      "first_404": "2026-04-15",
      "last_check": "2026-06-15",
      "last_status": 404
    }
  }
}
```

Rules:

- Use `safe_get_bytes` (or a HEAD-only wrapper using the same URL allowlist)
  so SSRF protection and size caps apply.
- One HEAD per URL per run. No retries on transient failures (5xx, timeout)
  — only 4xx in the 400 family increments `404_count`. A 200 or 3xx
  resets `404_count` and clears `first_404`.
- Idempotent: running twice in a row updates `last_check` but the
  `404_count` / `first_404` only move on actual status change.
- Optional `--since` flag: skip URLs whose `last_check` is newer than the
  given ISO date. Used by the runner to throttle: "check at most once a
  day per URL."

Failure handling: per-URL errors are recorded but never halt the run.

### 2. `scout report` — daily and weekly rollups

Reads `/command-center/threads/*.jsonl` and produces a markdown summary.

```sh
uv run scout report                     # today's rollup, printed
uv run scout report --week              # last 7 days
uv run scout report --week --write      # also commit to reports/
uv run scout report --since 2026-06-01  # custom range
```

Rollup shape (markdown):

```markdown
# Scout health report — 2026-06-08 → 2026-06-14

## Headline

- Runs: 14 (12 ok, 2 partial)
- Candidates queued: 412 (incl. 287 via repo extraction)
- Identity / URL collapses by dedup: 38
- Merge proposals surfaced: 11 active, 3 carried (rejected)
- Catalog auto-archived: 2 (1 superseded, 1 source-url-404)

## By agent

| Agent              | Runs | OK | Partial | Notable failures                  |
| ------------------ | ---: | -: | ------: | --------------------------------- |
| scout              |    7 |  6 |       1 | reddit 403 (known)                |
| scout-extract-repo |    5 |  3 |       2 | 2× clone-runner exit 128 (disk)   |
| scout-dedup        |    2 |  2 |       0 | —                                 |

## By source

| Source        | Queued | Errors | Notable                                  |
| ------------- | -----: | -----: | ---------------------------------------- |
| hackernews    |    382 |      0 | first-run cursor flood                   |
| awesome-lists |     27 |      0 | one new list added                       |
| reddit        |      0 |      7 | residential IP 403 (see runbook)         |
| lobsters      |      3 |      0 |                                          |

## Token burn

(no LLM-driven agents emitted token records this week — reviewer agent
not yet implemented)

## Things to triage

- 6 repo extractions failed with "fatal: write error: No space left on
  device" — host disk pressure during the run.
- 1 repo aborted on symlink in `.claude/` (Imbad0202/academic-research-skills).
  Expected; security baseline is doing its job. No further action.
```

Where the report lives when `--write` is passed:

```
/command-center/token-burn/reports/
  2026-06-08-week.md       # the weekly rollup (Mon-Sun by convention)
  2026-06-15.md            # daily rollups when written explicitly
```

(The `token-burn/` directory hosts both kinds of report; the name is a
historical artifact from Phase 0 and not worth renaming.)

### 3. `scout doctor` — catalog integrity checks

Static checks over `/catalog/` and `/scout/queue/`:

- **Orphan children:** any asset with `relations.parent: <slug>` whose
  parent isn't in `/catalog/` or `/scout/queue/`.
- **Broken supersedes:** `relations.supersedes: [<slug>]` where the
  named slug doesn't exist.
- **Slug ↔ filename mismatches.**
- **Required-field gaps** (per `catalog/_schema/asset.schema.md`).
- **Stale `status: reviewed`** older than 30 days (informational; pass 4
  of the dedup engine handles the auto-archive subset).

```sh
uv run scout doctor              # summary
uv run scout doctor --json       # machine-readable
uv run scout doctor --fix        # fix what's safely auto-fixable (slug
                                 #   normalization only — never destructive)
```

Doctor failures don't halt anything — they're reviewer fodder. Exit code
`0` always unless `--strict` flag is passed.

### 4. Token-burn schema (forward-looking)

The thread log gains optional fields the rollup understands:

```json
{
  "thread_id": "reviewer-2026-06-15-103000",
  "agent": "scout-reviewer",
  "model": "claude-opus-4-7",
  "input_tokens": 12345,
  "output_tokens": 678,
  "cache_read_tokens": 0,
  "cache_write_tokens": 0,
  "tool_calls": 5,
  "ended_at": "...",
  "outcome": "ok",
  "summary": "..."
}
```

Existing scout / scout-dedup / scout-extract-repo records continue to
work because they don't carry these fields and the rollup treats them
as zeros.

**The agents that emit these don't exist yet — that's Phase 8+.** Phase
7 lands the schema and the rollup math so when a reviewer agent emits
tokens, the report column lights up without further changes.

### 5. Runner integration

`scout run` runs the URL-liveness checker as a tail step (throttled to
once per URL per day) so catalog freshness is maintained without an
operator-level cron.

```python
# in runner.run_once, after the dedup pass:
if run_liveness:
    check_urls_once(since=today - timedelta(days=1))
```

Skipped with `--no-check-urls`. The dedup pass that follows reads the
fresh data.

## Failure modes & required handling

| Failure                                                | Action                                                                       |
| ------------------------------------------------------ | ---------------------------------------------------------------------------- |
| URL HEAD times out / DNS fails                         | Record per-URL error; continue. Don't increment `404_count` on a 5xx / network failure. |
| Liveness state corrupt / unparseable                   | Back up the file as `url-liveness.json.broken-<ts>`; start fresh. Warn in stats. |
| Thread log file missing (no runs in the window)        | Empty rollup; exit 0 with a "no data" notice in the report.                  |
| Catalog file unparseable during `doctor`               | Report the file; skip; continue with the rest.                               |
| Report `--write` target already exists for the same period | Overwrite. The report is a pure function of inputs; not destructive.    |

## Code surface (rough)

New files:

```
scout/
  liveness/
    __init__.py
    check.py             URL liveness HEADer + state writer
  report/
    __init__.py
    aggregate.py         JSONL → in-memory rollup
    render.py            rollup → markdown
    cli.py               glue
  doctor/
    __init__.py
    checks.py            orphan-child, broken-supersedes, slug mismatch, …
    cli.py
scout/state/
  url-liveness.json      (gitignored runtime; created by `scout check-urls`)
command-center/token-burn/reports/
  README.md              what these files are; convention
```

Updated files:

```
scout/agent/cli.py       + `check-urls`, `report`, `doctor` subcommands
scout/agent/runner.py    + invoke liveness tail step in run_once (toggle-able)
command-center/README.md + section on running rollups
docs/runbooks/scout-run.md + section on the new commands
```

New tests:

```
tests/unit/
  test_liveness_check.py        HEAD logic, streak counting, idempotency
  test_report_aggregate.py      JSONL → totals
  test_report_render.py         totals → markdown snapshot
  test_doctor_checks.py         orphan / broken-supersedes / slug-mismatch
tests/integration/
  test_run_once_with_liveness.py  scout run → liveness state → dedup pass 4 fires
  test_report_end_to_end.py       fixture JSONLs → committed report; idempotent
tests/fixtures/
  liveness/                       sample state file shapes
  reports/expected/               snapshot markdown for render tests
  thread-logs/                    sample JSONL inputs
```

## Open questions to resolve during the session

1. **Where do reports live?** `/command-center/token-burn/reports/` (matches
   the existing scaffold) vs a new `/command-center/reports/` (more
   honest naming). *Recommendation: `/command-center/token-burn/reports/`
   in v1. Renaming the directory is a separate concern; reports going in
   there is the substance.*
2. **Daily vs weekly default.** `scout report` with no args — print
   today's rollup, or last 7 days? *Recommendation: today by default; `--week`
   for the 7-day rollup. Most operator queries are "what happened today."*
3. **Should `--write` always commit?** Or just write the file and let the
   operator commit by hand? *Recommendation: write only. Committing is
   the operator's call; surprising auto-commits are a footgun.*
4. **Liveness throttle policy.** Once per day per URL is the obvious
   default. Should we ALSO add a global per-run cap (don't HEAD more than
   N URLs per `scout run` tick)? *Recommendation: yes; cap at 50 per
   tick. The catalog is small enough that a full pass happens in days,
   not minutes. Reviewer can override with `scout check-urls` directly.*
5. **`scout doctor --fix` scope.** What counts as "safely auto-fixable"?
   *Recommendation: slug ↔ filename normalization only (filename change
   if the slug is stable). Anything else — orphan children, broken
   supersedes — surfaces to the reviewer, never auto-resolves.*

Each open question gets answered in the commit; the answer moves into
`locked_decisions:` on this plan's frontmatter at phase close.

## Task breakdown (suggested execution order)

| #  | Task                                                                                       | Parallelizable with |
| -- | ------------------------------------------------------------------------------------------ | ------------------- |
| 1  | Implement `scout/liveness/check.py` + `scout check-urls` CLI.                              | 2                   |
| 2  | Wire liveness tail step into `runner.run_once` (with throttle + `--no-check-urls`).        | 1                   |
| 3  | Implement `scout/report/aggregate.py` (JSONL → totals, pure function).                     | 4                   |
| 4  | Implement `scout/report/render.py` (totals → markdown).                                    | 3                   |
| 5  | Wire `scout report [--week] [--since] [--write]` CLI.                                      | 6                   |
| 6  | Implement `scout/doctor/checks.py` + `scout doctor` CLI.                                   | 5                   |
| 7  | Define the optional token-burn schema fields in thread-log convention; document.           | 8                   |
| 8  | Unit tests: liveness counting, aggregate math, render snapshot, doctor checks.             | 7                   |
| 9  | Integration test: `scout run` writes liveness → dedup archives a fixture asset.            | 10                  |
| 10 | Integration test: fixture JSONLs → committed report; idempotent re-render.                 | 9                   |
| 11 | Update `command-center/README.md` and `docs/runbooks/scout-run.md`.                        | 12                  |
| 12 | Quality gate: `uv run ruff check`, `uv run pytest`, `uv run pytest tests/integration`.     | 13                  |
| 13 | Commit as one logical change. Flip plan to `status: done`; finalise `locked_decisions:`. Rename session prompt to `phase-7-observability.done.md`. |

## Quality gate (must all pass before commit)

```sh
uv run ruff check scout/ tests/
uv run pytest -q
uv run pytest tests/integration -q
# Smoke (manual):
uv run scout check-urls -v        # at least one HEAD landed; state file written
uv run scout report               # prints today's rollup without errors
uv run scout doctor               # exit 0 (warnings are fine)
```

The liveness smoke must not HEAD more than 50 URLs (the throttle works).
The report smoke must produce valid markdown with no empty sections.

## Commit message (template for task 13)

```
Phase 7: command-center observability

- scout/liveness/: URL liveness HEAD-er + state writer. Wired into
  scout run as a throttled tail step. Feeds dedup pass 4.
- scout/report/: JSONL aggregator + markdown renderer; `scout report`
  with --week / --since / --write. Reports land under
  /command-center/token-burn/reports/.
- scout/doctor/: catalog integrity checks (orphan children, broken
  supersedes, slug↔filename mismatch).
- Token-burn schema fields added to the thread-log convention so future
  LLM-driven agents emit input_tokens / output_tokens and the rollup
  picks them up without further changes.
- command-center/README.md + docs/runbooks/scout-run.md: new commands.
- docs/plans/phase-7-observability.md: status -> done; locked decisions
  finalised.
- docs/plans/session_prompts/phase-7-observability.done.md: archived.
```

## When this plan becomes stale

Status flips to `done` when the commit lands. If a later phase replaces
the markdown-rollup approach with something richer (a web view, a real
TSDB), write a new plan that `supersedes: [phase-7-observability]`. Until
then this plan is the authoritative design for what observability looks
like in this repo.
