---
name: phase-8-3b-triage-frontend-prompt
title: "Session prompt — Phase 8.3b triage frontend + cascade"
kind: session-prompt
phase: 8
status: active
related: [phase-8-3b-triage-frontend]
created_at: 2026-06-17
updated_at: 2026-06-17
---

# Session prompt — Phase 8.3b triage frontend

Paste the block below as the opening message to a fresh Claude Code
session in `/code/autoclaude` to execute this sub-phase. The
substantive plan is canonical in-repo at
`/docs/plans/phase-8-3b-triage-frontend.md`; this prompt sequences
the cold-start reads and pins what landed in the previous session.

The previous session shipped:

- Phase 8.3 hardening (commit `f529f45`): `commit_created` on every
  write response + audit row, `NothingToCommit` + `must_commit`,
  409 `target-exists` / 404 `target-not-found` translations, 12-item
  extended dogfood, findings doc.
- Catalog grew 13 → 20.
- Recommendation: 8.3b frontend next (curl is tolerable but slug
  munging is the dominant friction; UI removes it before 9.0 adds
  load).

This session lands a **narrow** triage frontend (NOT a full CRUD
UI) plus one small backend correctness fix (G1: parent-rename
cascade in `triage_keep`).

---

```
We are starting Phase 8.3b of the autoclaude repo. The previous
session shipped 8.3 hardening (commit f529f45): audit-honesty,
`commit_created` wired through write-back, error translations,
extended dogfood. The findings doc recommended 8.3b frontend next.

This session has two goals:
  1. Build the minimum triage UI that lets the operator empty the
     ~340-item queue at click-pace (5–10s per item).
  2. Close G1 (parent-rename cascade) — a 30-line backend fix the
     hardening dogfood surfaced.

Out of scope: full catalog edit, frontmatter cleanup, diff preview,
9.0 reviewer agent, auth.

Read these in order before doing anything else:

  1. CLAUDE.md                                          (operating brief)
  2. /docs/plans/phase-8-3b-triage-frontend.md          (THIS plan; full read)
  3. /docs/plans/phase-8-3-hardening-findings.md        (the friction we're
                                                         removing; S1–S4)
  4. /docs/plans/phase-8-3-hardening.md                 (locked decisions
                                                         from the immediate
                                                         predecessor)
  5. /conventions/web-app.md                            (frontend rules —
                                                         §7 in particular)
  6. /command-center/runbooks/web-app.md                (boot sequence;
                                                         bump `last_verified`
                                                         after smoke)
  7. /web/apps/web/app/queue/page.tsx                   (the SSR shell we
                                                         extend, not replace)
  8. /web/apps/web/lib/api.ts                           (typed client; we
                                                         add 2 methods)
  9. /web/apps/web/lib/api-types.ts                     (wire types; we
                                                         add 1 model)
  10. /web/apps/api/writes/triage.py                     (file G1 changes —
                                                         the cascade hook)
  11. /web/apps/api/routers/catalog.py                   (where the new
                                                         /catalog/exists/
                                                         endpoint lives)
  12. /web/apps/api/writes/audit.py                      (the result blob
                                                         schema)
  13. /tests/integration/web/test_write_back.py          (style for the
                                                         cascade test)
  14. /tests/integration/web/test_api_catalog.py         (style for the
                                                         exists endpoint
                                                         tests)

Then check tree state:

  git status --short                                    # MUST be clean
  git log --oneline -5                                  # expect f529f45 on top

Confirm the API + frontend boot:

  rm -rf web/.data
  AUTOCLAUDE_API_PORT=8765 uv run autoclaude-api &
  curl -s http://localhost:8765/health | jq            # ok: true
  curl -s http://localhost:8765/stats | jq '.stats.by_bucket.queue'
  kill %1
  ( cd web/apps/web && npm install && npm run build )  # next build clean

Locked decisions from prior sessions (do NOT relitigate):

- Markdown remains canonical; DB is derived.
- Routers don't open files / DB sessions directly.
- `commit_created` is on every write response + audit row.
- `triage_discard` is the only writer that passes must_commit=False.
- Server Components by default; client only for interactivity.
- No data caching across requests (`cache: "no-store"`).
- Tailwind utilities + `lucide-react`.

Two tasks for this session:

  TASK 1 — Backend G1 (cascade) + slug-exists endpoint.
    Per the plan §1 and §2.

    a. Add `GET /catalog/exists/{slug}` to routers/catalog.py
       returning `{exists: bool}`. Pydantic model
       `SlugExistsResponse`. Mirror in api-types.ts.

    b. In writes/triage.py::triage_keep, when target_slug differs
       from the candidate's old name field, walk /scout/queue/*.md
       and rewrite `relations.parent` from old to new. Idempotent
       and best-effort (malformed queue file = skipped + logged,
       not 500).

    c. Audit row: include `result.cascaded_children: int` count.

    d. Tests:
         - test_api_catalog.py: exists True/False cases.
         - test_write_back.py: triage_keep with rename cascades to
           2 fixture children, audit count matches.
         - test_writes_triage.py (new unit): pin the cascade helper
           on a temp tree.

    e. Quality gate: ruff + pytest -q. Both green.

  TASK 2 — Frontend triage UI.
    Per the plan §3.

    a. lib/api.ts:
         - queue.triage(slug, body): POST /queue/{slug}/triage
         - catalog.slugExists(slug): GET /catalog/exists/{slug}

    b. New directory components/triage/:
         - useTriage.ts          (hook returning state + 3 methods)
         - TriageActionsBar.tsx  (3 buttons + opens right modal)
         - KeepModal.tsx         (slug input + live collision check)
         - MergeModal.tsx        (target autocomplete via
                                  catalog.list({q}))
         - DiscardModal.tsx      (notes textarea)
         - TriageToast.tsx       (success/error vocabulary mapping)

    c. app/queue/page.tsx: import + render TriageActionsBar per row.
       The SSR list shell stays. The bar is a client component.

    d. Error vocabulary mapping (in TriageToast):
       - 409 version-mismatch  → "file changed — refresh + retry"
       - 409 target-exists     → link to colliding catalog file
       - 409 dirty-tree        → "working tree dirty on this path"
       - 404 target-not-found  → forces operator back to autocomplete
       - 422                   → field-level message
       Unknown: raw body in <code>.

    e. Frontend tests (Jest + React Testing Library):
         - KeepModal: slug input debounce + green/red state
         - TriageActionsBar: each button calls the right hook method
       (If Playwright isn't yet set up, defer the e2e to a separate
        infrastructure task — don't block on it.)

    f. Quality gate: cd web/apps/web && npm run lint && npm run
       test && npm run build. All green.

  TASK 3 — Operator dogfood-2 (exit gate).
    Per the plan §6.

    a. Boot the API on 8765 and the frontend on 3000.
    b. 30-minute timer. Triage at least 60 candidates through the
       UI (mix of keeps + merges + discards).
    c. Capture:
         - total wall-clock,
         - average seconds/item,
         - any UX surprise that made the operator hesitate,
         - any case the operator wished a button existed but didn't.
    d. Append a "Dogfood-2 (UI pass)" section to
       /docs/plans/phase-8-3-hardening-findings.md with the data
       and a clear next-session recommendation:
         - per-item time < 10s → 8.4 catalog edit
         - per-item time still painful → 9.0 reviewer agent

  TASK 4 — Commit + close out.
    - Single commit per the plan template. Bundle backend +
      frontend + tests + plan updates + dogfood findings.
    - Flip /docs/plans/phase-8-3b-triage-frontend.md
      status -> done, completed_at -> today, finalise
      locked_decisions.
    - Rename this prompt to phase-8-3b-triage-frontend.done.md.
    - Leave phase-8-web-command-center status: active.

Out of scope for this session (do NOT start):

  - Catalog detail edit pages / FrontmatterForm / BodyEditor.
  - The `scout:` frontmatter cleanup on keep.
  - Engagement / threads workflow surfaces.
  - 9.0 reviewer agent (LLM proposals).
  - Diff preview pane in any modal.
  - Auth / multi-operator.

Stay inside the contract: this sub-phase ships the minimum surface
that unblocks the queue backlog, NOT a complete operator console.

When done, summarize:
  - tasks landed,
  - test counts before/after (Python + TS),
  - ruff + npm-lint + npm-build status,
  - queue + catalog counts before/after the dogfood,
  - dogfood-2 timings + recommendation,
  - commit SHA.
```

---

## Why this prompt is shaped this way

- **Three tasks ordered by dependency.** G1 + slug-exists ship
  first (TASK 1) so the frontend has a real backend to point at.
  Frontend (TASK 2) lands second. Dogfood (TASK 3) closes the
  session and produces the next-session signal. TASK 4 is
  housekeeping.
- **Narrow on purpose.** The biggest risk is scope creep into "let
  me add a diff preview" or "let me also fix the scout: leak."
  Both are tempting; both are explicitly out of scope. The plan
  exists to hold the line.
- **Dogfood is the deliverable.** The UI is a means. The number
  the dogfood produces is what informs the next session's fork.
- **The session ends with a measurable.** "Per-item time" is the
  one number that makes the 9.0-vs-8.4 decision concrete. Don't
  forget to capture it.

## When this file becomes stale

`status: active` while Phase 8.3b is in flight. When the commit
lands and dogfood-2 is captured, rename to
`phase-8-3b-triage-frontend.done.md`. If a future session changes
the UI shape fundamentally, write a successor prompt rather than
editing this one.
