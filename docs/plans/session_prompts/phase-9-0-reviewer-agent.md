---
name: phase-9-0-reviewer-agent-prompt
title: "Session prompt — Phase 9.0 reviewer agent"
kind: session-prompt
phase: 9
status: active
related: [phase-9-0-reviewer-agent, phase-8-3b-triage-frontend]
created_at: 2026-06-17
updated_at: 2026-06-17
---

# Session prompt — Phase 9.0 reviewer agent

Paste the block below as the opening message to a fresh Claude Code
session in `/code/autoclaude` to execute this phase. The
substantive plan is canonical in-repo at
`/docs/plans/phase-9-0-reviewer-agent.md`; this prompt sequences
the cold-start reads, pins what landed in the previous sessions,
and flags which of the plan's 18 tasks are already-done or stale.

## Preconditions before this session fires

This phase plugs into the operator's existing approve/reject loop.
Run it **only after**:

- Phase 8.3b has committed (look for the commit "Phase 8.3b: narrow
  triage frontend + parent-rename cascade" on `main`).
- The dogfood-2 timings have been appended to
  `phase-8-3-hardening-findings.md` and the recommendation in that
  file points at 9.0 (not 8.4).

If the dogfood data points at 8.4 instead, skip this prompt and
run the 8.4 session first. The 9.0 plan keeps.

## What the previous sessions shipped (cumulative)

- **8.3 backend** (commit `236dd26`): write-back + proposals table +
  accept/reject endpoints + audit log.
- **8.3 dogfood** (commit `9bfcc71`): two bug fixes; orphan
  committed; findings doc.
- **8.3 hardening** (commit `f529f45`): `commit_created` on every
  write response + audit row; `NothingToCommit` + `must_commit`;
  409 `target-exists` / 404 `target-not-found`; extended dogfood;
  hardening-findings doc.
- **8.3b triage UI** (commit TBD by previous session): inline
  keep/merge/discard with slug-collision check and target
  autocomplete; G1 parent-rename cascade in `triage_keep`; eval-gate
  measured per-item triage time.

The 8.3b commit makes one thing concrete that the 9.0 plan only
sketched: **proposals already render in the UI**. When this session
ships agent-generated proposals, the operator approves/rejects them
through the same `TriageActionsBar` flow they already use for
manual triage. No new approve/reject UI is needed.

## What's stale in the 9.0 plan vs. what's still load-bearing

The plan was authored in commit `fee4b8c` (pre-8.3-hardening,
pre-8.3b). Read it in full, then apply these adjustments:

| Plan task                                                            | Status now                                                  |
| -------------------------------------------------------------------- | ----------------------------------------------------------- |
| **Tasks 1–10** (agent code: schema, prompt, context, budget, runner) | **Load-bearing.** Build as written.                         |
| **Task 11** (operator review v0 golden set → 30 items)               | **Load-bearing**, easier than written — the operator now triages golden-set items through the 8.3b UI, so labelling is a side-effect of normal use. |
| **Task 12** (eval runner)                                            | **Load-bearing.** Build as written.                         |
| **Task 13** (`/command-center/runbooks/scout-review.md`)             | **Load-bearing but lighter** — the runbook now references the existing UI, not a hypothetical one. |
| **Task 14** (`/conventions/merge-rules.md` update)                   | **Mostly redundant** — 8.3 hardening already locked the proposal-table workflow. Light edit only, if any. |
| **Tasks 15–18** (CLAUDE.md, quality gate, dry-run, live run, commit) | **Load-bearing.** Run as written.                           |

---

```
We are starting Phase 9.0 of the autoclaude repo. The previous
sessions shipped:
  - 8.3 backend, dogfood, hardening (commits 236dd26, 9bfcc71,
    f529f45) — write-back, proposals table, audit honesty.
  - 8.3b triage UI (commit on main, look for "Phase 8.3b") — the
    operator can already approve/reject proposals via the same
    inline keep/merge/discard flow used for manual triage.

This session ships the LLM reviewer agent that *generates*
those proposals from queue items, with prompt-cached system +
rules + schema, a budget cap, and an eval harness gating ship.

Read these in order before doing anything else:

  1. CLAUDE.md                                          (operating brief)
  2. /docs/plans/phase-9-0-reviewer-agent.md            (THIS plan; full read)
  3. /docs/plans/phase-8-3b-triage-frontend.md          (what just shipped;
                                                         the UI you plug into)
  4. /docs/plans/phase-8-3-hardening-findings.md        (dogfood-1 + dogfood-2
                                                         data — the operator
                                                         friction the agent
                                                         must beat)
  5. /scout/reviewer/evals/golden.jsonl                 (v0 17-item draft set)
  6. /conventions/merge-rules.md                        (the rules the agent
                                                         must enforce)
  7. /conventions/security.md                           (what the agent must
                                                         NOT do: no shell, no
                                                         network beyond the
                                                         Claude API, no
                                                         writes outside
                                                         /proposals)
  8. /command-center/token-burn/                        (the JSONL schema the
                                                         budget tracker emits)
  9. /web/apps/api/routers/proposals.py                 (the existing
                                                         /proposals API the
                                                         agent POSTs to)
  10. /web/apps/api/models.py                            (CreateProposalRequest;
                                                         the wire shape)
  11. /scout/_security.py                                (the locked-flag the
                                                         agent's HTTP client
                                                         must honour)

Then check tree state:

  git status --short                                    # MUST be clean
  git log --oneline -8                                  # find the 8.3b
                                                         commit on top

  # Read the dogfood-2 timings the previous session captured:
  grep -A 20 "Dogfood-2 (UI pass)" \
    docs/plans/phase-8-3-hardening-findings.md

If the dogfood-2 recommendation in that file is "8.4 catalog edit"
instead of "9.0 reviewer agent", STOP and consult with the operator
before continuing. The premise of this session is that 9.0 is the
right next step; if the data disagrees, the data wins.

Confirm the Anthropic SDK key is available:

  printenv ANTHROPIC_API_KEY | wc -c                    # > 0

If unset, ask the operator to `export ANTHROPIC_API_KEY=...`
before continuing. The agent makes real API calls; eval and dry-run
both spend tokens.

Locked decisions from prior sessions (do NOT relitigate):

- Markdown remains canonical; DB is derived.
- Routers don't open files / DB sessions directly.
- Optimistic locking via `version` stays.
- `commit_created` is on every write response + audit row.
- 409 codes: `version-mismatch`, `target-exists`, `dirty-tree`.
  404: `target-not-found`. The agent's failures map to these.
- `triage_discard` is the only writer with `must_commit=False`.
- The proposal table + accept/reject endpoints + UI are done.
  This phase only writes TO the table; the operator's UI consumes.
- Server Components by default; client only for interactivity.
- No data caching across requests on the frontend.

NEW locked decisions for this phase (lock them in the plan when
the commit lands):

- The reviewer agent NEVER writes to `/catalog/`, `/scout/queue/`,
  or `/web/.data/` directly. It only POSTs to `/proposals`.
- Every API call uses `cache_control: ephemeral` on the system,
  rules, and schema blocks. Per-candidate context is the only
  un-cached portion. (See plan §3, "prompt-caching plumbing".)
- The agent stops dead at the daily budget cap. The cap is a
  hard refusal, not a soft warning.
- Model default: claude-sonnet-4-6. Opus escalation only when
  the schema-validator rejects the Sonnet response.

Six tasks for this session, in order:

  TASK 1 — Plan triage + scope confirmation.
    a. Read the 9.0 plan and the dogfood-2 timings.
    b. Identify which of the plan's 18 tasks are stale per the
       table in this prompt's preamble. Quote each in the
       commit message later.
    c. If the plan's task list needs changes beyond what this
       prompt's table says, amend the plan in place (small edit)
       and explain in the commit message.

  TASK 2 — Agent code (plan tasks 1–10).
    Build the modules in this order — each is small enough to
    test before moving on:

    a. `scout/reviewer/schema.py`  — Decision model + validators.
    b. `scout/reviewer/prompt.py`  — system + rules + cache markers.
    c. `scout/reviewer/context.py` — substring + tag-overlap retrieval.
    d. `scout/reviewer/budget.py`  — JSONL budget tracker; price table.
    e. `scout/reviewer/agent.py`   — one-candidate review; retries.
    f. `scout/reviewer/runner.py`  — batch driver; proposal POSTs;
                                     JSONL emit; escalation.
    g. `scout/reviewer/cli.py`     — wire into `scout/agent/cli.py`.

    Each module gets unit tests next to it (SDK mocked). The
    runner gets an integration test against an httpx-stubbed
    Anthropic + a TestClient-wrapped FastAPI.

  TASK 3 — Eval harness (plan tasks 11–12).
    a. Operator review of the v0 golden set (17 items) using the
       8.3b UI — produces clean labels. If the operator hasn't
       finished labelling, the eval harness runs on what's labelled
       and reports coverage.
    b. `scout/reviewer/eval.py`: load golden.jsonl, run the agent
       against each item with the proposal POST mocked, score
       action-match (overall, per class) and slug-suggestion
       accuracy. Hard gate at 90% discard agreement / 80%
       keep-rename slug match.
    c. `uv run scout review --evals` runs the harness and prints a
       confusion matrix.

  TASK 4 — Runbook + convention touchpoints (plan tasks 13–14).
    a. `/command-center/runbooks/scout-review.md`: how to run the
       agent, how to set the budget cap, how to inspect proposals
       in the UI, how to clear stale proposals.
    b. `/conventions/merge-rules.md`: light edit only if anything
       in the rules changed; the 8.3-hardening pass already locked
       the proposal-table workflow.

  TASK 5 — Dry-run smoke (plan task 16).
    a. 5 real queue items selected by the operator (the v0 golden
       set is fine).
    b. `uv run scout review --dry-run --candidates <slugs>` — the
       agent runs but the proposal POST is logged-only (no DB
       writes). Verify each Decision validates and the budget
       tracker recorded the spend.

  TASK 6 — Live run (plan task 17).
    a. Budget cap: $5 for this session.
    b. `uv run scout review --batch 50` — produces up to 50
       pending proposals.
    c. Operator reviews a sample in the 8.3b UI; accepts or
       rejects via the existing buttons.
    d. Capture: total spend, items processed, action distribution,
       any pathological proposal (mass-discard, mass-keep, etc).

  TASK 7 — Commit + close out.
    - One commit per the plan's commit template. Bundle code +
      tests + runbook + plan-status update.
    - Flip /docs/plans/phase-9-0-reviewer-agent.md
      status -> done; completed_at -> today; finalise
      locked_decisions.
    - Rename this prompt to phase-9-0-reviewer-agent.done.md.
    - Append a "Phase 9.0 — first live run" section to
      `/command-center/threads/` (whichever date file is current)
      with the live-run telemetry from TASK 6.

Out of scope for this session (do NOT start):

  - Semantic search / pgvector context retrieval. Substring +
    tag-overlap only. Vectors are 9.x.
  - Auto-accept / auto-merge. Every proposal is operator-gated,
    always. No "high-confidence skips review" path.
  - Multi-agent debate / second-opinion reviewer. One agent.
  - Hosted / cron runner. Local invocation only.
  - Cost optimisation beyond budget cap + Sonnet/Opus escalation.
  - Generating frontmatter from scratch. Suggest fixes only.
  - Editing existing catalog entries via the agent. The agent
    works on queue items, not catalog. (8.4 territory.)

When done, summarize:
  - which plan tasks landed, which were stale-skipped,
  - test counts before/after (Python),
  - ruff status,
  - eval scores (per-class confusion matrix),
  - dry-run + live-run spend,
  - number of pending proposals produced,
  - operator's first-pass approve/reject ratio,
  - any rough edges or surprises,
  - the commit SHA,
  - next-session recommendation (probably 8.4 catalog edit, OR
    9.x semantic-search context if the eval scores under-shoot).
```

---

## Why this prompt is shaped this way

- **Conditional firing.** This session presupposes 8.3b's dogfood
  data points at 9.0 and not 8.4. The prompt makes that explicit
  and asks the session to stop if the data disagrees. Wasted
  sessions cost more than wasted prompts.
- **Stale-task table front-and-centre.** The 9.0 plan was authored
  before 8.3 hardening + 8.3b. Rather than rewrite it in place, the
  prompt overlays a small table that tells the session which tasks
  are still load-bearing. The commit message preserves that
  decision audit.
- **`ANTHROPIC_API_KEY` precondition.** This is the first phase
  that costs real money. The prompt makes the operator's setup
  step explicit so the session doesn't fail an hour in.
- **Eval gate is non-negotiable.** Hard gate at 90% discard
  agreement / 80% slug match. Shipping a 70% reviewer fills the
  proposal queue with garbage that's *worse* than no agent at all
  (operator now has to read every proposal AND every candidate).
- **Live-run telemetry → threads log.** Phase 7 set up the
  threads log for exactly this kind of "thing happened, here's
  the spend" record. Use it.

## When this file becomes stale

`status: active` while Phase 9.0 is in flight. When the commit
lands and the live-run telemetry is in the threads log, rename to
`phase-9-0-reviewer-agent.done.md`. If 9.x or 9.5 needs a
different agent shape (semantic search, second reviewer, hosted
runner), write a successor prompt rather than editing this one.
