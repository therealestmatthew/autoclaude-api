---
name: phase-6-merge-dedup-prompt
title: "Session prompt — Phase 6 (automated merge / dedup decisioning)"
kind: session-prompt
phase: 6
status: done
related: [phase-6-merge-dedup]
created_at: 2026-06-15
updated_at: 2026-06-15
---

# Session prompt — Phase 6 (automated merge / dedup decisioning)

Paste the block below as your opening message to a fresh Claude Code session in `/code/autoclaude`. The substantive plan is canonical in-repo at `/docs/plans/phase-6-merge-dedup.md`; this prompt just sequences the cold-start reads.

---

```
We are starting Phase 6 of the autoclaude repo. The full plan is in-repo at:

  /code/autoclaude/docs/plans/phase-6-merge-dedup.md

Read that plan IN FULL before doing anything else, then read these in
order (all small):

  1. CLAUDE.md                            (operating brief; note "Planning lineage")
  2. conventions/merge-rules.md           (the decision tree this phase
                                           implements as code; you will add an
                                           "Automation" section to this file)
  3. conventions/testing.md               (test directory + protocol)
  4. conventions/frontmatter.md           (you will read AND write `status:`,
                                           `mergeset_id:`, `archived_reason:`,
                                           `archived_at:`)
  5. catalog/_schema/asset.schema.md      (the asset shape the engine reads/edits)
  6. scout/_util.py                       (slugify, canonical_github_url,
                                           parse_frontmatter — all four passes
                                           rely on these)
  7. scout/agent/runner.py                (the orchestrator you will plug a
                                           final dedup pass into)
  8. scout/agent/types.py                 (Candidate, SourceState — the engine
                                           reads SourceState for 404 streaks)
  9. scout/extractors/repo.py             (Phase 4 — read enough to know how
                                           children carry `relations.parent` and
                                           `fingerprint:`, which the engine uses
                                           as identity keys)
  10. docs/plans/phase-4-repo-extractor.md (locked decisions about parent/child
                                            scoping that Phase 6 must not
                                            re-litigate; specifically: cross-
                                            repo child collisions are NOT dups)

Then check working-tree state with `git status --short`. The tree should
be clean at the start of Phase 6 — confirm before beginning, and ask if
it isn't.

ALSO look at the live state of the queue and the catalog:

  ls scout/queue/ | wc -l                   # how many candidates pending
  ls catalog/ | wc -l                       # how many catalog assets
  uv run scout run -v --no-dedup            # only if newer signal is desired

A representative queue + catalog snapshot is the only way to know if
your Jaccard / threshold tuning is reasonable. The expected starting
state is ≥300 queue files dominated by post-Phase-4 child Candidates;
if it's much smaller, ask the user before proceeding (someone may have
reviewed the queue between phases).

Locked decisions (do NOT relitigate):

- Reviewer trust model: human-only for *promotion* to /catalog/. The
  engine does triage and grouping, not final decisions. (Phases 0/3/4.)
- Auto-archive is allowed on objective signals only (404 source for >30
  days; supersedes chain). Auto-promote is NEVER allowed.
- Merge proposals are written to the queue file's body, not applied
  destructively. (Set in this phase.)
- Fingerprints are sha256 over canonical bytes (file bytes for repo
  children; URL for top-level candidates). (Phase 4.)
- Cross-repo child collisions are NOT duplicates. The slug already
  namespaces them by parent (<repo-a>--code-reviewer vs
  <repo-b>--code-reviewer). The engine does NOT collapse these. It
  MAY surface them as `relations.related[]` proposals under tighter
  conditions (Jaccard ≥ 0.8 AND same primary author). (Phase 6.)
- v1 is deterministic-rules-only. NO embedding models, NO LLM-classifier.
  Re-examine in a later phase if the deterministic rules leave clear
  gaps. (Phase 6.)

Open questions called out in the plan, to be resolved in this session
and moved into `locked_decisions:` in the plan's frontmatter at close:

1. Where rejected merge proposals live (recommend BOTH a body section
   for humans and a JSONL ledger as the engine's source of truth).
2. Jaccard threshold (recommend ship at 0.6; tune from real data).
3. Auto-archive for queue 404s (recommend keep with body note, do NOT
   discard — the 404 itself is signal).
4. Cross-kind dedup on URL (recommend YES, collapse to the `repo`
   member because it carries Phase 4 extraction potential).
5. Sibling-child cross-repo dedup (recommend NO collapse; surface as
   `relations.related[]` only at Jaccard ≥ 0.8 AND same primary author).

Execute the plan's numbered tasks (1–12) in order. Tasks 2/7 and 1/10
parallelize cleanly via subagents.

Quality gate before commit (must all pass):

  uv run ruff check scout/ tests/
  uv run pytest -q
  uv run pytest tests/integration -q
  uv run scout dedup --dry-run        # smoke; must report >0 identity collapses
  uv run scout run -v                  # confirm thread log records the pass
                                       # counts

Idempotency check (REQUIRED): run `uv run scout dedup` twice. Second
run MUST produce identical state. If it doesn't, you have an
oscillation bug — fix before committing.

Commit as ONE logical change using the commit message template in the
plan's task 12. Do not split.

Out of scope for this session (do not start):
- Phase 5 (X / Twitter) — separate plan.
- Phase 7 (command-center observability).
- Auto-promotion of any kind. Promotion is human-only forever.
- LLM-based or embedding-based classification. Phase 6 is
  deterministic-rules-only.
- Edits to /catalog/ that touch anything other than the four
  allowlisted status-change fields (`status`, `archived_reason`,
  `archived_at`, and bumping `updated_at`).

When done, summarize: tests passing count, ruff status, dry-run results
(passes counts: identity / URL / proposals / auto-archive), idempotency
check result, the resolution of each of the five open questions, the
commit SHA, and any rough edges that surfaced (especially: any
unexpectedly-aggressive merge proposals that the reviewer would clearly
reject). Then flip the plan's frontmatter to `status: done`, set
`completed_at`, finalise `locked_decisions:`, and rename this prompt
file to `phase-6-merge-dedup.done.md`.
```

---

## Why this prompt is shaped this way

- **Live-state snapshot before code.** Phase 6 is the first phase whose tuning depends on the actual shape of the queue. The reading list ends with a "look at the live state" step so the implementer's Jaccard threshold isn't decided from theory.
- **Locked decisions inline, including the negative ones.** "Cross-repo child collisions are NOT duplicates" and "v1 is deterministic-only" are *exactly* the kinds of things a session is most likely to relitigate without explicit instruction. Naming them in the prompt prevents waste.
- **Idempotency check as a hard gate.** A non-idempotent dedup is worse than no dedup. The prompt makes the second-run check a merge requirement, not an afterthought.
- **Plan-first, in-repo.** Same lineage rule as Phases 4 and 5.

## When this file becomes stale

Rename to `phase-6-merge-dedup.done.md` once Phase 6 commits cleanly (per the closing task in the plan).
