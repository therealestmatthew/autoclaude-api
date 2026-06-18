---
name: phase-8-3-hardening-prompt
title: "Session prompt — Phase 8.3 hardening + extended dogfood"
kind: session-prompt
phase: 8
status: active
related: [phase-8-3-hardening]
created_at: 2026-06-17
updated_at: 2026-06-17
---

# Session prompt — Phase 8.3 hardening

Paste the block below as your opening message to a fresh Claude Code
session in `/code/autoclaude` to pick up this sub-phase. The substantive
plan is canonical in-repo at `/docs/plans/phase-8-3-hardening.md`; this
prompt sequences the cold-start reads and pins what landed in the
previous session.

The previous session shipped:
- Phase 8.2 persistent index (commit `04f619d`).
- 8.3 plan + 9.0 plan (commit `fee4b8c`).
- v0 reviewer-eval golden set + 7 plan corrections (commit `aa06eda`).
- F1 retraction after a `scout dedup` dry-run (commit `e974e66`).
- Phase 8.3 backend (commit `236dd26`).
- First dogfood pass: two real bugs found, two regression tests, orphan
  catalog file committed, three plan deltas captured (commit `9bfcc71`).
- A real catalog grew from 9 → 11 via dogfood.

This session picks up W1 + W3 (audit-honesty fix) and a second dogfood
pass against 10–15 harder candidates.

---

```
We are continuing Phase 8.3 of the autoclaude repo. The previous
session shipped the 8.3 backend, ran a dogfood pass against the real
queue, and committed two bug fixes + a findings doc. Three deltas
remain — W1, W2, W3 in
`docs/plans/phase-8-3-dogfood-findings.md`. This session lands the
two correctness ones (W1, W3) and validates the fix with another
dogfood pass.

Read these in order before doing anything else:

  1. CLAUDE.md                                       (operating brief)
  2. /docs/plans/phase-8-3-hardening.md              (THIS sub-phase's
                                                      canonical plan;
                                                      read in full)
  3. /docs/plans/phase-8-3-dogfood-findings.md       (what the first
                                                      dogfood surfaced;
                                                      especially W1, W3)
  4. /docs/plans/phase-8-3-write-back.md             (parent plan; you
                                                      need the failure-
                                                      mode table)
  5. /conventions/web-app.md                         (the contract for
                                                      anything under /web/)
  6. /command-center/runbooks/web-app.md             (operator runbook;
                                                      bump `last_verified`
                                                      after you smoke)
  7. /web/apps/api/writes/git.py                     (the file W1 changes)
  8. /web/apps/api/writes/editor.py                  (callers of commit())
  9. /web/apps/api/writes/triage.py                  (callers; note
                                                      triage_discard is
                                                      the must_commit=False
                                                      case)
  10. /web/apps/api/writes/audit.py                   (W3: result field)
  11. /web/apps/api/models.py                         (Pydantic; W3 wire)
  12. /web/apps/api/routers/writes.py                 (translates exceptions
                                                      to HTTP)
  13. /tests/integration/web/test_write_back.py       (regression tests
                                                      added in 9bfcc71;
                                                      extend their
                                                      `commit_created`
                                                      assertions)
  14. /scout/reviewer/evals/golden.jsonl              (v0 draft labels;
                                                      the dogfood batch
                                                      pulls from here)

Then check tree state:

  git status --short                                  # MUST be clean
  git log --oneline -5                                # expect 9bfcc71 on top

Confirm the API still boots cleanly:

  rm -rf web/.data
  AUTOCLAUDE_API_PORT=8765 uv run autoclaude-api &
  curl -s http://localhost:8765/health | jq          # ok: true; records > 0
  curl -s http://localhost:8765/stats | jq '.stats.by_bucket'
  kill %1

Locked decisions from prior sessions (do NOT relitigate):

- Markdown remains canonical; DB is derived.
- Routers don't do I/O — including DB sessions (8.2 § routers).
- Optimistic locking via `version` (8.3 § §5).
- `triage_discard` of a gitignored queue file produces no commit.
  That is correct behaviour, not a failure.
- The PK on `asset` is `path`, not `(bucket, slug)`. The dogfood
  doesn't change this.
- The v0 golden labels (`labeled_by: claude-draft-2026-06-17`) are
  drafts. The reviewer eval gate refuses to use them.

Two tasks for this session:

  TASK 1 — W1 + W3 correctness fix.
    Per phase-8-3-hardening.md § Design steps 1–3:

    a. Add `NothingToCommit` exception + `must_commit: bool = True`
       parameter to `web/apps/api/writes/git.py::commit()`. Change
       its return shape from `str` to `tuple[str, bool]` (sha,
       commit_created). When must_commit=True and is_anything_staged
       returns False, raise NothingToCommit. When must_commit=False
       and nothing staged, return (head_sha, False).

    b. Update the five callers in writes/editor.py and writes/triage.py
       to consume the tuple and pass the right must_commit value
       (triage_discard=False; everything else=True). Surface
       `commit_created` on WriteResult / TriageResult.

    c. Add `commit_created` to WriteResponse / TriageResponse in
       models.py and to the audit row's `result` dict.

    d. Mirror in `web/apps/web/lib/api-types.ts`.

    e. routers/writes.py: translate FileExistsError -> 409
       (`target-exists`) and FileNotFoundError -> 404
       (`target-not-found`) for triage.

    f. Unit tests:
         - `test_writes_git.py::test_commit_raises_nothing_to_commit_when_must`
         - `test_writes_git.py::test_commit_returns_false_when_optional`

    g. Update the existing gitignored-queue integration tests in
       `test_write_back.py` to assert `commit_created` matches
       expectation:
         - triage_discard_with_gitignored_queue -> False
         - triage_keep_with_gitignored_queue   -> True

    h. Quality gate: `uv run ruff check scout/ web/ tests/ tools/`
       and `uv run pytest -q`. Both green.

    i. Commit. Use the template in phase-8-3-hardening.md
       § "Commit message".

  TASK 2 — Extended dogfood (10–15 triages).
    Per phase-8-3-hardening.md § Design step 4. Boot the API on a
    spare port (8765 is what the prior session used), then drive
    triages via curl. Suggested batch from the v0 golden set:

      Easy keeps (4): claude-api-fundamentals-course,
                      use-the-claude-agent-sdk-with-your-claude-plan,
                      apple-foundation-models, academic-research-skills-for-claude-code
      Slug-rename keep (1): claude-code-as-a-daily-driver-... (use
                      target_slug=claude-code-daily-driver)
      Parent-child cascade (2): show-hn-skills-for-humanity-... parent +
                      one s4h-* child (try the parent first; observe
                      what happens to the child queue items)
      Hard discard (1): antirez-on-x-i-believe-what-anthropic-is-doing-...
      Easy discards (3+): pick from the remaining anthropic / white-
                      house / fable news cluster

    For each triage, record:
      - HTTP status + response body
      - commit_created (should match git history)
      - audit row's `result.commit_created` (sanity check against the
        response)
      - any friction or surprise (slug awkwardness, target conflict, ...)

    Note: keep triages may fail with 409 `target-exists` if the
    operator already created that catalog slug — that's the
    FileExistsError -> 409 path the W1 work added.

    Write a findings doc at
    `docs/plans/phase-8-3-hardening-findings.md` capturing:
      - What landed (counts: discards, keeps, queue size change,
        catalog size change)
      - Any bugs discovered + fixes
      - Cases the parent-child cascade made awkward (this is the
        biggest unknown going in)
      - A clear recommendation for the NEXT session: 8.3b frontend or
        9.0 reviewer agent

    Commit the findings doc (separate commit from TASK 1's bug fix
    commit; one is correctness work, the other is real-world data).

Out of scope for this session (do NOT start):

  - 8.3b frontend (FrontmatterForm, BodyEditor, TriagePanel,
    ProposalCard, catalog/[slug]/edit, proposals/). Next session's
    fork — let the findings doc inform the decision.
  - 9.0 reviewer agent. Same.
  - W2 cleanup (production-gitignore fixture). The two regression
    tests are enough until we need a third write-back test.
  - Cleaning up the scout: block carried into catalog entries by
    triage_keep. That's a frontmatter-form concern; 8.3b owns it.
  - Operator review of the 17-item v0 golden set. Separate workflow.

When done, summarize:
  - which tasks landed,
  - test counts before/after,
  - ruff status,
  - the catalog + queue counts before/after the dogfood,
  - any rough edges,
  - the commit SHAs (TASK 1 and the findings commit),
  - the next-session recommendation (8.3b vs 9.0) with reasoning.

Then mark `/docs/plans/phase-8-3-hardening.md` `status: done`, set
`completed_at`, finalise the `locked_decisions:` list, and rename
this prompt file to `phase-8-3-hardening.done.md`. Leave the
overarching `phase-8-web-command-center` plan `status: active`.
```

---

## Why this prompt is shaped this way

- **Two tasks, one session.** TASK 1 (correctness fix) is small and
  well-scoped — under an hour of careful work. TASK 2 (dogfood) is
  cheap, generates real data, and is the only way to make a confident
  call between 8.3b and 9.0 for the session after this one. Together
  they fit in a single fresh-session window without sprawl.
- **Reading order is dependency-ordered.** The W1 + W3 work touches
  `git.py` (which the editor / triage layer wraps), and the audit
  row's `result` blob. Reading those three in the order above
  produces the right mental model before any edit.
- **The dogfood batch is pre-picked.** I named the specific slugs to
  triage so a fresh session doesn't have to re-do the queue
  reconnaissance that produced the v0 golden set. The picks span
  the cases the first dogfood missed (parent-child cascade, slug
  rename, famous-person discard) on purpose.
- **The next-session recommendation is the deliverable.** This
  sub-phase doesn't just close W1 + W3 — its output is also a real
  judgment about whether 8.3b frontend or 9.0 reviewer should come
  next, grounded in two passes of operator-friction data. That
  decision is too important to make on a guess.

## When this file becomes stale

`status: active` while Phase 8.3 hardening is in flight. When the
TASK 1 + findings commits land, rename this prompt to
`phase-8-3-hardening.done.md`. If a future session changes the
W1 / W3 design fundamentally, write a successor prompt rather than
editing this one.
