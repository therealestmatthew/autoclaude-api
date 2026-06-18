---
name: phase-8-3-frontend-followup-prompt
title: "Session prompt — Phase 8.3 frontend dogfood + residuals"
kind: session-prompt
phase: 8
status: active
related:
  - phase-8-3-write-back
  - phase-8-3-hardening
  - phase-8-3b-triage-frontend
  - phase-9-0-reviewer-agent
created_at: 2026-06-18
updated_at: 2026-06-18
---

# Session prompt — Phase 8.3 frontend dogfood + residuals

Paste the block below as your opening message to a fresh Claude Code
session in `/code/autoclaude` to pick up the 8.3 follow-up. The
canonical plans are in-repo at `/docs/plans/phase-8-3-write-back.md`
(now `status: done`) and `/docs/plans/phase-8-3b-triage-frontend.md`
(largely absorbed; remaining items listed below). This prompt
sequences the cold-start reads and pins what landed in the previous
session.

The previous session shipped:

- Phase 8.3 backend (`236dd26`).
- Phase 8.3 hardening — W1 audit honesty + W3 `commit_created` +
  extended dogfood (`f529f45`).
- Phase 8.3 frontend — FrontmatterForm, BodyEditor, TriagePanel,
  ProposalCard, `/catalog/[slug]/edit`, extended `/queue/[slug]`,
  `/proposals`, new `GET /catalog/{slug}/raw` (`c22fc4e`).

This session picks up: (1) a real browser-driven dogfood of the new
write-back surface, (2) the parent/child rename cascade gap (G1 from
8.3b), and (3) two small UX polishes that pre-empt the most common
4xx errors.

---

```
We are continuing Phase 8.3 of the autoclaude repo. The previous
session landed the 8.3 operator frontend — catalog editor, queue
triage panel, proposals inbox — and a new `GET /catalog/{slug}/raw`
route so the editor round-trips every frontmatter key. The backend
write service has been dogfooded twice via curl; the UI has NOT been
dogfooded yet.

Three tasks for this session. Read first, then plan, then execute.

Read these in order before doing anything else:

  1. CLAUDE.md                                       (operating brief)
  2. /docs/plans/phase-8-3-write-back.md             (just-completed
                                                      8.3 plan; status
                                                      done; reads as
                                                      the contract for
                                                      what's wired)
  3. /docs/plans/phase-8-3-hardening-findings.md     (what the second
                                                      dogfood surfaced;
                                                      the parent-child
                                                      cascade gap is
                                                      called out as G1)
  4. /docs/plans/phase-8-3b-triage-frontend.md       (the original
                                                      narrow-frontend
                                                      plan; most of its
                                                      scope is now
                                                      absorbed — only
                                                      G1 + the two
                                                      polish items
                                                      remain)
  5. /conventions/web-app.md                          (the contract for
                                                      anything under /web/)
  6. /command-center/runbooks/web-app.md             (operator runbook;
                                                      bump `last_verified`
                                                      after you smoke)
  7. /web/apps/api/writes/triage.py                  (where the G1 fix
                                                      lives — read
                                                      triage_keep + see
                                                      how the rename
                                                      doesn't currently
                                                      cascade to
                                                      relations.parent)
  8. /web/apps/api/routers/catalog.py                (the new /raw
                                                      route; the
                                                      editor relies on
                                                      it)
  9. /web/apps/web/components/FrontmatterForm.tsx    (today's editor)
 10. /web/apps/web/components/TriagePanel.tsx        (today's triage UI;
                                                      where the slug-
                                                      collision check
                                                      and merge-target
                                                      autocomplete land)
 11. /web/apps/web/lib/api.ts                        (existing client
                                                      helpers — extend
                                                      these, don't
                                                      bypass)

Then check tree state:

  git status --short                                  # MUST be clean
  git log --oneline -5                                # expect c22fc4e on top

Confirm the API + UI still boot cleanly:

  AUTOCLAUDE_API_PORT=8765 uv run autoclaude-api &
  curl -s http://localhost:8765/health | jq          # ok: true; records > 0
  curl -s http://localhost:8765/catalog/<some-slug>/raw | jq '.frontmatter | keys'
  ( cd web/apps/web && NEXT_PUBLIC_API_URL=http://localhost:8765 npm run dev ) &
  # then visit http://localhost:3000/catalog/<some-slug>/edit in a browser
  # and confirm the form renders the typed fields + the JSON editors.
  kill %1 %2

Locked decisions from prior sessions (do NOT relitigate):

- Markdown is canonical; DB is derived.
- Routers do no I/O; the write service is the only writer.
- Optimistic-lock token is the SHA-256 of raw file bytes; the UI
  passes it as `expected_version`.
- The editor uses `GET /catalog/{slug}/raw`, not `GET /catalog/{slug}`.
  Required so saves don't lose untyped frontmatter keys (`fingerprint`,
  `scout`, etc.).
- `next.config.mjs` has `experimental.typedRoutes` OFF — the codebase
  uses template-string hrefs that the experiment rejects.
- The 8.3b plan is partially absorbed; only G1 (parent-rename cascade)
  and the two polish items survive.

Three tasks for this session:

  TASK 1 — Browser dogfood of the write-back UI.
    Boot the API + Next.js dev server (commands above). Then:

      a. Edit one real catalog asset's frontmatter via
         /catalog/<slug>/edit. Pick a slug whose frontmatter has an
         untyped field (`fingerprint` or `scout` — `anthropic-on-aws`
         is a confirmed example; verify with the /raw endpoint first).
         Make a small change (e.g. add a tag), save, and confirm:
           - the response shows commit_created=true
           - `git log -1 -- catalog/<slug>.md` shows the new commit
           - the file's `fingerprint` / `scout` keys are still intact
             (this is the round-trip safety the /raw route enables)
      b. Edit a body via the same page. Confirm commit + content.
      c. Trigger a 409 deliberately: edit the file from the terminal
         between loading the page and clicking Save. Confirm the
         banner appears, the Reload button refreshes, and the second
         save succeeds.
      d. Triage one real queue candidate via /queue/<slug> using each
         action (keep, merge, discard) on three different candidates.
         For merge, point at an existing catalog slug so we exercise
         the 404 `target-not-found` path (try a bad target first to
         verify the error UX).
      e. Visit /proposals. With no reviewer-agent rows yet the list
         should be empty; the filter form should still render and
         "Apply" should round-trip. Optionally `POST /proposals` from
         curl to seed one operator-source row and confirm
         accept/reject work end-to-end.

    Write a findings doc at
    /docs/plans/phase-8-3-frontend-dogfood-findings.md capturing:
      - which actions worked vs. surprised
      - any 4xx the UI surfaced poorly
      - friction (especially around the JSON-editor textareas in
        FrontmatterForm — that's the part most likely to be too raw)
      - a concrete recommendation on whether to ship as-is or pull
        in any of the TASK 3 polishes immediately

  TASK 2 — G1: parent/child rename cascade.
    See phase-8-3b-triage-frontend.md § G1. When a catalog asset is
    renamed via triage_keep (target_slug differs from the queue slug),
    any other asset with `relations.parent: <old-slug>` is silently
    left dangling. Fix:

      a. In /web/apps/api/writes/triage.py::triage_keep, when the
         target_slug differs from the existing catalog slug (rare —
         but it's the parent-rename case during a real merge), find
         all catalog files whose `relations.parent == <old>` and
         rewrite them to `<new>`. Same write-service path: each child
         goes through serialize.replace_frontmatter + atomic_write +
         git.commit. The cascade should produce ONE commit per child
         (or a single squashed commit — design choice; pick the one
         that's easier to read in `git log`).
      b. Surface a `cascade: [{slug, new_parent}, ...]` field on the
         TriageResponse so the UI can show what got rewritten.
      c. Mirror the field in `web/apps/web/lib/api-types.ts`.
      d. Show the cascade list in TriagePanel's success state ("also
         rewrote N child(ren): a, b, c") — one block under the audit
         line.
      e. Integration test: a parent + two children fixture; triage_keep
         the parent with a renamed target_slug; assert both children's
         `relations.parent` point at the new slug and that both child
         file mtimes / git history changed.
      f. Quality gate: `uv run ruff check scout/ web/ tests/ tools/`
         and `uv run pytest -q`. Plus `cd web/apps/web && npm run
         typecheck && npm run build`.

  TASK 3 — Two UX polishes (pre-empt the most common 4xx).
    Both live in the frontend; no backend change.

      a. Live slug-collision check on triage keep.
         TriagePanel: when action=keep and target_slug is non-empty,
         debounce a `GET /catalog/<target_slug>` against the API every
         300ms. If it returns 200, show a red inline marker
         ("target-exists: catalog/<slug>.md already exists") and
         disable the Submit button. If 404, show green ("slug is
         free"). This pre-empts the 409 `target-exists` path.

      b. Catalog-slug autocomplete on triage merge.
         TriagePanel: when action=merge, render the target_slug input
         as a combobox. On focus + on input, debounce a
         `GET /catalog?q=<text>&limit=20` and show the first 20
         matches as a dropdown. Each match shows slug + title. This
         pre-empts the 404 `target-not-found` path and is the single
         biggest friction reducer for merges.

    Both polishes are small (under ~80 LOC each). Use the existing
    `api.catalog.list`/`api.catalog.get` helpers — don't bypass api.ts.

Out of scope for this session (do NOT start):

  - Phase 9.0 reviewer agent. Has its own session prompt and is the
    next phase after this one.
  - Real-time multi-operator concurrency (real-time conflict
    resolution). Still 8.4+.
  - A general PR flow. Saves still commit straight to the working
    branch.
  - Cloud deploy (8.5). Still local-only.
  - Refactoring FrontmatterForm to drop the JSON-editor textareas in
    favor of fully typed fields for source/discovered/relations.
    That's a UX call to make AFTER the dogfood findings — could come
    in a 8.3d or be punted to 8.4.

When done, summarize:
  - which tasks landed,
  - test counts before/after,
  - ruff status,
  - the commit SHAs (recommend separate commits for TASK 1 findings,
    TASK 2 G1 fix, TASK 3 polish),
  - the next-session recommendation (Phase 9.0 reviewer agent is the
    expected next step; only deviate if the dogfood found something
    foundational).

Then:
  - If TASK 2 + TASK 3 both land: flip
    /docs/plans/phase-8-3b-triage-frontend.md `status: done` and
    rename this prompt to `phase-8-3-frontend-followup.done.md`.
  - If only some land: leave both files as-is and write a residual
    note at the top of the 8.3b plan.
  - Leave the overarching `phase-8-web-command-center` plan
    `status: active`.
```

---

## Why this prompt is shaped this way

- **Dogfood first.** The 8.3 backend was dogfooded via curl twice
  before the UI shipped. The UI itself has been compiled + smoke-
  tested but never operator-driven. TASK 1's findings are the input
  that decides whether to polish before 9.0 or move on.
- **G1 is small and self-contained.** It's the only residual
  correctness gap from 8.3b; it's a write-service change with a clear
  test shape. It can fit in the same session as the dogfood.
- **The two polishes are bounded.** Slug-collision check and merge
  autocomplete both pre-empt 4xx paths users will otherwise hit
  immediately. They are bounded (~80 LOC each) and use existing API
  helpers. Doing them now beats waiting until the operator complains.
- **9.0 is the expected next step.** This session is a tight wrap-up
  of 8.3 before the reviewer-agent phase. The session prompt for 9.0
  already exists at `/docs/plans/session_prompts/phase-9-0-reviewer-agent.md`.

## When this file becomes stale

`status: active` while the 8.3 frontend follow-up is in flight. When
TASK 2 + TASK 3 land, rename this prompt to
`phase-8-3-frontend-followup.done.md`. If a future session
fundamentally rethinks the editor (e.g. drops the JSON-editor
textareas in favor of fully typed source/discovered/relations forms),
write a successor prompt rather than editing this one.
