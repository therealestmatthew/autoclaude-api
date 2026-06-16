---
name: phase-7-observability-prompt
title: "Session prompt — Phase 7 (command-center observability)"
kind: session-prompt
phase: 7
status: active
related: [phase-7-observability]
created_at: 2026-06-15
updated_at: 2026-06-15
---

# Session prompt — Phase 7 (command-center observability)

Paste the block below as your opening message to a fresh Claude Code session
in `/code/autoclaude`. The substantive plan is canonical in-repo at
`/docs/plans/phase-7-observability.md`; this prompt just sequences the
cold-start reads.

---

```
We are starting Phase 7 of the autoclaude repo. The full plan is in-repo at:

  /code/autoclaude/docs/plans/phase-7-observability.md

Read that plan IN FULL before doing anything else, then read these in
order (all small):

  1. CLAUDE.md                              (operating brief; note "Planning lineage")
  2. command-center/README.md               (mental model of the dir you're building into)
  3. command-center/threads/README.md       (the JSONL shape you are aggregating)
  4. command-center/token-burn/README.md    (where rollup reports land)
  5. conventions/security.md                (safe_get_bytes / safe_external_url —
                                             the liveness checker uses these)
  6. scout/_security.py                     (the helpers; you will reuse them for HEAD)
  7. scout/agent/runner.py                  (the orchestrator you will plug
                                             a liveness tail step into; same
                                             pattern as the Phase 6 dedup tail)
  8. scout/dedup/archive.py                 (pass 4 — it reads url-liveness.json;
                                             your check-urls writes it)
  9. scout/agent/cli.py                     (the surface you extend with
                                             check-urls / report / doctor)
  10. docs/plans/phase-6-merge-dedup.md     (locked decisions about how
                                             pass 4 consumes the liveness state;
                                             specifically: the engine is
                                             network-free, the checker is not)

Then check working-tree state with `git status --short`. The tree should
be clean at the start of Phase 7 — confirm before beginning, and ask if
it isn't.

ALSO look at:

  ls command-center/threads/*.jsonl | wc -l         # how many days of data
  cat command-center/threads/$(date -I).jsonl | wc -l   # today's record count
  ls catalog/ | wc -l                                # how many URLs to HEAD

If `command-center/threads/` has <2 days of data, the report rendering
will look thin. Seed with `uv run scout run` (offline-safe; HN may queue
zero on a dry day) before testing.

Locked decisions (do NOT relitigate):

- Markdown-first. Rollups are markdown committed to
  /command-center/token-burn/reports/. No DB, no Grafana, no web UI.
- Thread logs stay append-only JSONL at /command-center/threads/<date>.jsonl.
- Operator-pull, not push. No Slack / email / pager integration.
- Token-burn schema lands NOW even though no LLM-driven agent emits
  tokens yet — the plumbing is ready when reviewer/curator agents land.
- The dedup engine STAYS network-free. The URL-liveness checker is a
  separate command that POPULATES the state the engine reads. Do not
  fold the liveness check into scout dedup.

Open questions called out in the plan, to be resolved in this session
and moved into `locked_decisions:` in the plan's frontmatter at close:

1. Reports directory name (recommend /command-center/token-burn/reports/
   in v1; renaming is a separate concern).
2. Daily vs weekly default for `scout report` (recommend today by
   default; --week for the 7-day rollup).
3. `--write` behavior (recommend write-only; never auto-commit).
4. Liveness throttle policy (recommend once per URL per day AND a 50-URL
   cap per `scout run` tick).
5. `scout doctor --fix` scope (recommend slug ↔ filename normalization
   ONLY; orphan children + broken supersedes surface to the reviewer).

Execute the plan's numbered tasks (1–13) in order. Tasks 3/4 and 5/6
parallelize cleanly via subagents.

Quality gate before commit (must all pass):

  uv run ruff check scout/ tests/
  uv run pytest -q
  uv run pytest tests/integration -q
  uv run scout check-urls -v      # smoke; ≤50 URLs HEADed
  uv run scout report              # smoke; valid markdown
  uv run scout doctor              # smoke; exit 0

Idempotency check (REQUIRED):

- Run `uv run scout check-urls` twice; the second run updates
  `last_check` only — `404_count` / `first_404` must not move on
  unchanged status.
- Run `uv run scout report --write` twice; the committed report file
  must be byte-identical on the second write.

Commit as ONE logical change using the commit message template in the
plan's task 13. Do not split.

Out of scope for this session (do not start):
- A reviewer / curator / promotion agent. That's Phase 8+.
- Real-time dashboards, web UI, push notifications.
- Distributed thread aggregation across machines.
- Anything that moves token-burn from "schema + math" to "agent emitter."
  The emitter is whatever agent comes next; Phase 7 only ships the
  reader / aggregator / renderer.

When done, summarize: tests passing count, ruff status, smoke results
(check-urls URL count + writes, report shape, doctor warnings),
idempotency check results, the resolution of each of the five open
questions, the commit SHA, and any rough edges that surfaced (especially:
liveness HEAD requests that look unsafe or were rejected by safe_get_bytes).
Then flip the plan's frontmatter to `status: done`, set `completed_at`,
finalise `locked_decisions:`, and rename this prompt file to
`phase-7-observability.done.md`.
```

---

## Why this prompt is shaped this way

- **Liveness-first reading order.** Pass 4 of the dedup engine already
  reads the state file; the checker just populates it. Reading
  `scout/dedup/archive.py` before writing `scout/liveness/check.py`
  keeps the data shape consistent.
- **Locked decisions inline, including "engine stays network-free".**
  Without that lock, a fresh session is likely to fold the liveness
  check into `scout dedup` for tidiness — and break the determinism
  contract Phase 6 just established.
- **Token-burn schema separated from emitter.** The schema lands now
  precisely so the next phase (a reviewer agent) doesn't have to extend
  the rollup at the same time as building the agent.
- **Idempotency check is two-shaped.** Liveness and report each have
  their own definition of "identical second run." Naming both upfront
  prevents the implementer from declaring victory on just one.

## When this file becomes stale

Rename to `phase-7-observability.done.md` once Phase 7 commits cleanly
(per the closing task in the plan).
