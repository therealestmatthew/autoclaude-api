---
name: phase-8-3b-triage-frontend
title: "Phase 8.3b — triage frontend (narrow) + cascade-on-rename"
phase: 8
status: draft
created_at: 2026-06-17
updated_at: 2026-06-17
completed_at:
supersedes: []
superseded_by:
related:
  - phase-8-web-command-center
  - phase-8-3-write-back
  - phase-8-3-hardening
  - phase-8-3-hardening-findings
  - phase-9-0-reviewer-agent
locked_decisions: []
---

# Phase 8.3b — narrow triage frontend + parent-rename cascade

## Goal

The 8.3 backend works, the curl loop works, but the operator has
~350 queue candidates and a curl loop where each triage costs
30–60 seconds of slug-pasting and version-hash-pasting. Build the
smallest possible web UI that turns that loop into a click-per-item
pace, and close one specific correctness gap (G1, parent-child
rename cascade) that the hardening dogfood surfaced.

The deliverable is a queue page where the operator can:

- See each candidate's title, URL, kind, and a 3-line body preview.
- Click `keep`, `merge`, or `discard` inline.
- For `keep`: choose a slug, see a live red marker if the slug
  collides with an existing catalog file (pre-empting 409 *target-
  exists*).
- For `merge`: type a few characters and pick from a catalog-slug
  autocomplete (pre-empting 404 *target-not-found*).
- For `discard`: type a one-line reason and submit.
- See immediate success/failure feedback. On success the row
  optimistically disappears from the list and a toast links to the
  new (or unchanged) catalog entry.

Output: a backend-unchanged-except-for-G1 repo with a queue page
that lets the operator empty the backlog at a felt rate of 5–10
seconds per item.

## Non-goals (out of scope)

- **Catalog detail edit pages.** No FrontmatterForm / BodyEditor in
  this sub-phase. Defer to 8.4. The triage modals are intentionally
  the minimum surface area for the queue workflow.
- **Diff preview pane.** A nice-to-have, but the keep/merge/discard
  shapes are mechanical enough that the operator doesn't need to
  see the diff before submit. Defer.
- **Frontmatter cleanup on keep.** The `scout:` block still carries
  through. Comes with 8.4 catalog edit.
- **Engagement / threads workflow surfaces.** Untouched in this
  sub-phase.
- **9.0 reviewer agent.** Separate fork. The proposals API and DB
  table are already there; teaching an LLM to write to them is a
  different session.
- **Auth.** Single-operator local-dev assumption holds. 8.5+ owns
  multi-operator.

## Constraints (inherited + new)

Inherited:

- Markdown is canonical; the DB is a derived index.
- Routers don't open files / DB sessions directly.
- Every write produces a single git commit OR no commit at all,
  and the audit row reflects reality (8.3 hardening).
- Optimistic locking via `version` stays.
- Frontend: Server Components by default; client components for
  interactivity, opt-in via `"use client"` (`/conventions/web-app.md`).
- Tailwind utilities + `lucide-react` for icons.

New for this sub-phase:

- **Optimistic UI is allowed on the queue page** (the row disappears
  before the API confirms) **but only after the API responds 200**.
  Don't render success before the network roundtrip; do hide the
  row immediately after.
- **Every modal must show the failure code prominently.** The
  failure-mode taxonomy that 8.3 hardening shipped (`version-
  mismatch`, `target-exists`, `target-not-found`, `dirty-tree`) is
  the operator-facing vocabulary. Don't hide it behind a generic
  "something went wrong."
- **Triage modals are client components, but the queue list itself
  remains a Server Component.** The list is the SSR'd shell; a
  client component overlay (`TriageActionsBar`) provides the
  interactivity on each row. This keeps the SSR-by-default
  convention intact.

## Design

### 1. Backend additions (small)

The 8.3 backend already supports everything the UI needs except one
read-only ergonomic endpoint:

```python
@router.get("/catalog/exists/{slug}")
def catalog_slug_exists(slug: str, index: CachedIndex = Depends(get_index)) -> dict:
    """Return `{exists: bool}`. Used by the KeepModal to flash a
    live collision warning before submit. Cheaper than catalog.get()
    (no body load, no 404 round-trip)."""
```

Pydantic model:

```python
class SlugExistsResponse(BaseModel):
    exists: bool
```

Mirrors `api-types.ts`. That's the only new wire shape.

### 2. G1 — cascade parent-rename in `triage_keep`

When `triage_keep` is called with a `target_slug` that differs from
the candidate's current `name:` field, the writer also rewrites any
queue file whose `relations.parent` matches the **old** name to the
new name.

```python
# writes/triage.py, inside triage_keep, after deciding chosen_slug:
old_slug = fm.get("name") or source.stem
if target_slug and target_slug != old_slug:
    _cascade_parent_rename(repo_root, old=old_slug, new=target_slug)
```

The cascade walks `/scout/queue/*.md`, parses each file's
frontmatter, and rewrites `relations.parent` in place. Queue files
are gitignored so no commit is produced for the cascade — the
operator's subsequent `triage_keep` on each child will pick up the
new parent slug automatically.

Properties:

- **Idempotent.** A second run finds zero matches and is a no-op.
- **Best-effort.** A malformed queue file is skipped with a logged
  warning, not a 500. The cascade is a convenience, not a contract.
- **Atomic per-file.** Each rewrite is a single `atomic_write`. The
  cascade itself doesn't roll back if one file fails — partial
  cascades are valid (the operator just sees more parent-rename
  prompts later).

The audit row's `result.cascaded_children: int` counts how many
queue files were rewritten, so a later "what did this triage_keep
do?" query is answerable.

### 3. Frontend — components and routes

New files under `/web/apps/web/`:

```
app/queue/page.tsx                    # SSR list (already exists; light edits)
components/triage/
  TriageActionsBar.tsx                # client: 3 buttons + opens the right modal
  KeepModal.tsx                       # client: slug input + collision check + submit
  MergeModal.tsx                      # client: target autocomplete + submit
  DiscardModal.tsx                    # client: notes textarea + submit
  TriageToast.tsx                     # client: success/error banner
  useTriage.ts                        # client: hook wrapping the 3 POSTs + optimistic state
lib/api.ts                            # add `queue.triage()` and `catalog.slugExists()`
```

`app/queue/page.tsx` change: each row gets a `TriageActionsBar`
mounted as a client component below the existing card. The card
itself stays SSR.

#### `useTriage()` contract

```ts
type TriageState =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "success"; target_path: string | null; commit_created: boolean }
  | { kind: "error"; code: string; message: string };

function useTriage(slug: string, version: string): {
  state: TriageState;
  keep: (target_slug?: string) => Promise<void>;
  merge: (target_slug: string) => Promise<void>;
  discard: (notes: string) => Promise<void>;
  reset: () => void;
};
```

The hook owns the optimistic-hide logic: on `success` it calls a
parent callback that removes the row from the list immediately.

#### Slug-collision UX

The `KeepModal` debounces the slug input by 200ms, hits
`/catalog/exists/{slug}`, and shows:

- ✓ "slug is free" (green, small text under input)
- ✗ "slug collides with `catalog/<slug>.md`" (red, links to the
  existing catalog entry)

This pre-empts every 409 *target-exists* before the operator
clicks submit.

#### Autocomplete UX

`MergeModal` calls `api.catalog.list({ q: prefix, limit: 8 })` on
debounced input, renders results as a dropdown. The submit button
is disabled until the operator picks one (no free-text submits,
no 404 *target-not-found* surface).

#### Error rendering

All modals share `TriageToast`. On 200, toast is green with the
target path and a link. On a known code (409 `version-mismatch`,
409 `target-exists`, 409 `dirty-tree`, 404 `target-not-found`,
422), the toast is red and shows the code verbatim plus an actionable
hint:

- `version-mismatch` → "the file changed since this page loaded —
  refresh and retry."
- `target-exists` → link to the colliding catalog entry.
- `target-not-found` → "the target slug doesn't exist in the
  catalog."
- `dirty-tree` → "the working tree has uncommitted changes
  overlapping this path."

Unknown errors render the raw body in a `<code>` block. No silent
swallows.

### 4. Tests

Backend (Python):

- `tests/integration/web/test_api_catalog.py` — add
  `test_catalog_exists_returns_true_for_known` and
  `test_catalog_exists_returns_false_for_unknown`.
- `tests/integration/web/test_write_back.py` — add
  `test_triage_keep_with_rename_cascades_to_queue_children` (fixture
  has a parent + 2 children pointing at the parent; assert children's
  `relations.parent` is rewritten and the audit row's
  `result.cascaded_children == 2`).
- `tests/unit/web/test_writes_triage.py` (new) — pin the cascade
  helper on a temp tree.

Frontend (TypeScript):

- `tests/web/components/KeepModal.test.tsx` — slug-collision
  debounce + green/red state. (React Testing Library + jsdom.)
- `tests/web/components/TriageActionsBar.test.tsx` — the 3 buttons
  call the right hook method.
- One Playwright smoke (if Playwright isn't yet in the repo,
  defer to a separate setup task — don't block this sub-phase on
  CI plumbing).

### 5. Failure modes & required handling

| Failure                                       | UI handling                                                  |
| --------------------------------------------- | ------------------------------------------------------------ |
| 409 `version-mismatch`                        | Toast red. Suggest refresh. Row stays.                       |
| 409 `target-exists` (keep)                    | Pre-empted by live check. If somehow it still fires, toast + link to colliding catalog entry. |
| 404 `target-not-found` (merge)                | Pre-empted by autocomplete. If it fires, force the operator back to the autocomplete. |
| 409 `dirty-tree`                              | Toast red. Operator runs `git status` and stashes / commits. |
| 422 validation                                | Toast red with the field name. (`notes` required on discard, etc.) |
| Network error                                 | Toast red, "API unreachable." Row stays.                     |
| 500                                           | Toast red, raw body in `<code>`. Treat as a backend bug; file an issue. |

### 6. Operator dogfood (this sub-phase's exit gate)

When the UI ships, run a single 30-minute session through the queue:

- Target: at least 60 triage operations (keeps + discards).
- Track: total wall-clock time, average per-item time, any
  surprises, any case where the operator wished a button existed.
- Output: append a short "dogfood-2" section to
  `phase-8-3-hardening-findings.md` with numbers + decision input
  for 9.0 vs 8.4.

This data is the actual deliverable. The UI itself is a means.

## Task breakdown

| #  | Task                                                                                                | Notes                                  |
| -- | --------------------------------------------------------------------------------------------------- | -------------------------------------- |
| 1  | Backend: `GET /catalog/exists/{slug}` + `SlugExistsResponse` Pydantic + `api-types.ts` mirror.       | One endpoint, one model, one wire field. |
| 2  | Backend: G1 cascade in `triage_keep` + audit `result.cascaded_children` + tests.                    | One helper, idempotent, queue-only.    |
| 3  | Frontend: `lib/api.ts` — add `queue.triage()` and `catalog.slugExists()`.                          | Typed end-to-end.                      |
| 4  | Frontend: `useTriage` hook + three modals + `TriageActionsBar`.                                     | Five components.                       |
| 5  | Frontend: wire `TriageActionsBar` into `app/queue/page.tsx`.                                        | The SSR shell stays; client overlay.   |
| 6  | Frontend: `TriageToast` + error vocabulary mapping.                                                 |                                        |
| 7  | Backend tests for the new endpoint + cascade.                                                       |                                        |
| 8  | Frontend tests for `KeepModal` collision + `TriageActionsBar`.                                      | Jest + RTL.                            |
| 9  | Run quality gate: ruff + pytest + `cd web/apps/web && npm run lint && npm run test`.                | All green.                             |
| 10 | Operator dogfood: 30-minute session, ≥60 triages, capture timings + surprises.                      | Append to hardening-findings.          |
| 11 | Commit: backend + frontend in one commit per phase convention.                                      |                                        |
| 12 | Plan: `status: done`, `completed_at`, finalise `locked_decisions`.                                  |                                        |

## Quality gate (must all pass before commit)

```sh
uv run ruff check scout/ web/ tests/ tools/
uv run pytest -q

cd web/apps/web
npm install                                   # if needed
npm run lint
npm run test
npm run build                                  # next build catches type errors

# Smoke (manual, separate terminals):
rm -rf web/.data
AUTOCLAUDE_API_PORT=8765 uv run autoclaude-api &
( cd web/apps/web && NEXT_PUBLIC_API_URL=http://localhost:8765 npm run dev )
# Browse to http://localhost:3000/queue, run through the dogfood.
```

## Outcome → next session recommendation

The outcome of this sub-phase is **operator confidence** in the
manual triage loop and a **measured time-per-item** number. That
number decides the next session:

- **If per-item time < 10s** and the operator can stomach 30
  minutes of triage: clear the backlog by hand, then go 8.4
  catalog edit. The reviewer agent is interesting but not urgent.
- **If per-item time is still painful** (slug-rename overhead,
  discard-rationale fatigue): go 9.0 reviewer agent — the agent
  proposes, the operator approves at click-pace. The proposals
  table already exists; the UI now exists.

This plan does NOT pre-commit to the fork. The dogfood is the
input.

## Commit message (template)

```
Phase 8.3b: narrow triage frontend + parent-rename cascade (G1)

- web/apps/api/routers/catalog.py: GET /catalog/exists/{slug}.
- web/apps/api/writes/triage.py: cascade old->new parent slug
  across gitignored queue children on triage_keep rename.
  Audit row records cascaded_children count.
- web/apps/web/lib/api.ts: queue.triage(), catalog.slugExists().
- web/apps/web/components/triage/*: KeepModal, MergeModal,
  DiscardModal, TriageActionsBar, TriageToast, useTriage hook.
- web/apps/web/app/queue/page.tsx: mount TriageActionsBar per row.
- tests: backend cascade + slug-exists; frontend modals + bar.
- docs/plans/phase-8-3b-triage-frontend.md: status -> done.
- docs/plans/phase-8-3-hardening-findings.md: dogfood-2 timings
  appended; next-session fork chosen.

Dogfood: N triages in T minutes, P seconds/item average.
```

## When this plan becomes stale

`status: active` while the session is in flight. Flips to `done`
when the commit lands and the dogfood-2 timings are appended to the
hardening-findings doc. If the dogfood surfaces a UX redesign,
amend in place; a wholly new approach spawns a successor plan.
