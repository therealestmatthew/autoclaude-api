---
name: phase-5-x-twitter-prompt
title: "Session prompt — Phase 5 (X / Twitter ingestion)"
kind: session-prompt
phase: 5
status: done
related: [phase-5-x-twitter]
created_at: 2026-06-15
updated_at: 2026-06-15
---

# Session prompt — Phase 5 (X / Twitter ingestion)

Paste the block below as your opening message to a fresh Claude Code session in `/code/autoclaude`. The substantive plan is canonical in-repo at `/docs/plans/phase-5-x-twitter.md`; this prompt just sequences the cold-start reads.

---

```
We are starting Phase 5 of the autoclaude repo. The full plan is in-repo at:

  /code/autoclaude/docs/plans/phase-5-x-twitter.md

Read that plan IN FULL before doing anything else, then read these in
order (all small):

  1. CLAUDE.md                            (operating brief; note "Planning lineage")
  2. conventions/security.md              (sanitize_text + safe_get_bytes rules
                                           apply; bearer tokens never live in repo)
  3. conventions/testing.md               (test directory + protocol)
  4. scout/_security.py                   (helpers every extractor uses)
  5. scout/sources/x-handles.yaml         (the source config, currently disabled;
                                           the auth-question notes live here)
  6. scout/agent/types.py                 (Candidate, SourceState, and where the
                                           new XSource model registers)
  7. scout/agent/runner.py                (the orchestrator you will register into;
                                           note how Phase 4 added the queue-driven
                                           repo-extraction path AFTER the primary
                                           extractors — your XExtractor runs BEFORE)
  8. scout/extractors/awesome_list.py     (cleanest reference implementation;
                                           single-tier extractor without state cursors)
  9. scout/extractors/hackernews.py       (reference for state-cursor + dedup
                                           against state.seen_urls)
  10. catalog/_schema/asset.schema.md     (the target shape; X posts become
                                           kind: article with raw_url carrying any
                                           github.com/* link)

Then check working-tree state with `git status --short`. The tree should
be clean at the start of Phase 5 — confirm before beginning, and ask if
it isn't.

The FIRST decision in this session is the auth question (see plan §
"The auth question"). Pick one of:

  (a) Pay for X API Basic-tier ($100/mo). Full XExtractor lands.
  (b) Use a third-party aggregator (Nitter / Bluesky bridge). Adapter
      XExtractor lands; expect operational fragility.
  (c) Defer indefinitely. Ship XExtractor STUB that raises
      NotImplementedError; flip nothing else; update plan +
      x-handles.yaml notes; close the phase.

Default recommendation: (c). HN/Reddit echoes already catch the cross-
threshold signal; the long tail is mostly noise. If the user has not
explicitly said "pay for X", choose (c) and surface the decision in
the commit message.

Locked decisions (do NOT relitigate):

- Scout is discovery-only. X posts surface URLs; the Phase 4 repo
  extractor handles any github.com/* links on the next tick.
- Reviewer trust model is human-only. Candidates land in /scout/queue/,
  never directly in /catalog/.
- Every free-form X string runs through sanitize_text. Post bodies cap
  at 2000; titles at 300.
- Top-level posts only in v1 (not replies). One Candidate per github
  URL when ≥1 URL is present; otherwise one per post.
- Bearer tokens NEVER appear in the repo. Env var or
  ~/.config/autoclaude/x-bearer.env only.

Open questions called out in the plan, to be resolved in this session
and moved into `locked_decisions:` in the plan's frontmatter at close:

1. Pay / mirror / defer (THE primary decision, see above).
2. Bearer rotation policy (recommend env var, per-process load).
3. Per-URL vs per-post Candidates (recommend per-URL when present).
4. Right match.any_of for X specifically (recommend reuse HN list).
5. Replies vs top-level only (recommend top-level only in v1).

Execute the plan's numbered tasks (1–11) in order. Note: if the auth
answer is (c), the deliverable is small — tasks collapse to (1) write
stub, (6/7) doc updates, (10/11) gate + commit.

Quality gate before commit (must all pass):

  uv run ruff check scout/ tests/
  uv run pytest -q
  uv run pytest tests/integration -q

Plus, if (a) or (b), a manual smoke against the chosen surface (one
tick, ≥1 candidate queued, bearer/credentials not logged anywhere).

Commit as ONE logical change using the commit message template in the
plan's task 11. Do not split.

Out of scope for this session (do not start):
- Phase 6 (automated merge/dedup) — that plan is already drafted at
  /docs/plans/phase-6-merge-dedup.md; do not begin work on it here.
- Phase 7 (command-center observability).
- Reply trees, DMs, the social graph.
- Write operations of any kind (replies, follows, etc).

When done, summarize: which auth option you chose and why, the
resolution of each of the five open questions, tests passing count,
ruff status, the commit SHA, and any rough edges that surfaced. Then
flip the plan's frontmatter to `status: done`, set `completed_at`,
finalise `locked_decisions:`, and rename this prompt file to
`phase-5-x-twitter.done.md`.
```

---

## Why this prompt is shaped this way

- **Auth decision up-front.** Phase 5 has one decision that determines whether the rest of the session is "write a stub + close" or "write a full extractor + integration tests." Forcing that choice on the first turn prevents wasted exploration.
- **Plan-first, in-repo.** Same lineage rule as Phase 4 — the substantive plan lives in `/docs/plans/`, this prompt just sequences cold-start reads.
- **Reading list mirrors what an XExtractor implementer would actually need.** The two reference extractors (awesome_list — simple, hackernews — cursored) cover both shapes the X extractor might take.
- **Defer is the default.** The HN/Reddit echo path is doing real work already; paid API access is genuinely unclear-ROI for our cadence. Make the operator opt *in* to spending the money.
- **Phase 6 explicitly out-of-scope.** The next plan is already drafted; this prompt makes sure the session doesn't drift into it.

## When this file becomes stale

Rename to `phase-5-x-twitter.done.md` once Phase 5 commits cleanly (per the closing task in the plan).
