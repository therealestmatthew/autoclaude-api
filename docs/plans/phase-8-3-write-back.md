---
name: phase-8-3-write-back
title: "Phase 8.3 — Web command center write-back"
phase: 8
status: done
created_at: 2026-06-17
updated_at: 2026-06-18
completed_at: 2026-06-18
# 2026-06-17: backend landed; frontend deferred to 8.3b follow-up.
# 2026-06-18: frontend landed — FrontmatterForm, BodyEditor, TriagePanel,
# ProposalCard + catalog/[slug]/edit, extended queue/[slug], proposals/.
# New backend route GET /catalog/{slug}/raw added so the frontmatter
# editor round-trips every key (incl. extras like `fingerprint`/`scout`).
# Residuals: 8.3b's G1 (parent-rename cascade) + polish items
# (slug-collision live check, catalog-slug autocomplete on merge) — see
# docs/plans/session_prompts/phase-8-3-frontend-followup.md.
supersedes: []
superseded_by:
related: [phase-8-web-command-center, phase-8-2-persistent-index, phase-8-3-hardening, phase-8-3b-triage-frontend, phase-9-0-reviewer-agent]
locked_decisions:
  - "Editor uses GET /catalog/{slug}/raw (parsed full frontmatter dict + body + version), not /catalog/{slug}. Required so saves don't lose untyped frontmatter keys like `fingerprint`."
  - "Optimistic-lock token is the SHA-256 of raw file bytes (`raw_hash`). UI passes it back as `expected_version`; 409 banners offer a one-click reload."
  - "next.config.mjs experimental.typedRoutes is OFF; the codebase uses template-string hrefs that the experiment rejects."
---

# Phase 8.3 — Web command center write-back

## Goal

Turn the read-only web UI from 8.1/8.2 into a tool an operator actually
*uses*. Three concrete capabilities:

1. **Frontmatter editor.** A form-driven editor for `/catalog/<slug>.md`
   frontmatter, validated against the schema, that produces a single git
   commit per save.
2. **Body editor.** A textarea + preview for the markdown body, same git
   commit pattern.
3. **Queue triage.** A three-button UI on each queue candidate
   (`keep` / `merge` / `discard`) that performs the file rename / append /
   delete and commits the result.

All three flow through the same path: validate → write file → `git
commit` → record audit row → invalidate DB row. The web app becomes the
primary surface for the work that used to require manual markdown editing
and hand-crafted commits.

This milestone also lands the **proposal table** that Phase 9.0
(reviewer agent) writes into. Proposals are queue triage *recommendations*
that wait for operator approval through the same triage UI.

## Non-goals (out of scope for this milestone)

- **Multi-operator concurrency.** Two browsers editing the same asset
  simultaneously is solved with optimistic-lock 409s, not real-time
  conflict resolution. Real-time is 8.4+.
- **A general PR flow.** Saves commit straight to the working branch.
  Branch / review workflow is a later concern.
- **Diff editor.** Edits are full-document writes; we don't ship a
  three-way merge UI. If the file changed under us, we 409 and the
  operator re-fetches.
- **Pushing to a remote.** Commits land locally. The operator pushes
  by hand. Cloud deploy (8.5) revisits this when an always-on backend
  is the writer.
- **Rich-text / WYSIWYG.** Markdown source goes in; preview is rendered.
- **Auto-generating the reviewer agent's prompts.** That's 9.0.

## Constraints (inherited and new)

Inherited:

- Markdown remains canonical. Every write is a real file write + a real
  git commit. The DB row is the *index*, not the source.
- Routers do no I/O. The write-back surface lives behind a single
  service layer (`web/apps/api/writes/`) that the routers call.
- API surface stays typed (Pydantic in / out; TS mirror in `api-types.ts`).

New for 8.3:

- **Atomic-ish saves.** A failed write must not leave the system in a
  state where the file changed but no commit exists. Order of operations
  + a sweeper on next sync.
- **Optimistic locking.** Every GET response carries a `version` (=
  `content_hash` from the DB). Every PUT/POST asserts `If-Match: <hash>`.
  Mismatch → 409 with the current row attached.
- **Audit-first.** No write happens without an audit row. The audit is
  intent-then-outcome — the row is created in `pending` state before the
  file changes, and finalised after the commit lands.

## Design

### 1. Schema additions

Two new tables, one new column on `asset`.

```python
class Asset(Base):
    # ...
    # 8.3: optimistic-lock token. Tracks the content_hash the last
    # successful save observed. Same value as `content_hash` after sync;
    # diverges briefly during an in-flight write while the file has
    # been written but the sync hasn't re-read it yet.
    version = Column(String(64), nullable=False, default="")


class AuditEvent(Base):
    __tablename__ = "audit_event"

    id = Column(String(36), primary_key=True)           # uuid4
    created_at = Column(Float, nullable=False)          # epoch seconds
    updated_at = Column(Float, nullable=False)
    actor = Column(String(64), nullable=False)          # "operator" | "reviewer-agent" | future
    action = Column(String(64), nullable=False)         # see actions below
    target_path = Column(String(1024), nullable=False, index=True)
    target_bucket = Column(String(32), nullable=False)
    status = Column(String(16), nullable=False, index=True)  # pending | committed | failed
    intent = Column(JSON, nullable=False)               # the request payload, schema below
    result = Column(JSON, nullable=True)                # commit_sha, error, etc.
    notes = Column(Text, nullable=True)


class Proposal(Base):
    """Reviewer-agent recommendations (or operator drafts) awaiting a
    decision. Phase 9.0 fills this with `source = 'reviewer-agent'`
    rows; the triage UI surfaces them and writes the decision to the
    audit log on accept/reject."""

    __tablename__ = "proposal"

    id = Column(String(36), primary_key=True)
    created_at = Column(Float, nullable=False)
    source = Column(String(64), nullable=False, index=True)   # 'operator' | 'reviewer-agent'
    target_path = Column(String(1024), nullable=False, index=True)
    target_bucket = Column(String(32), nullable=False)
    action_kind = Column(String(32), nullable=False)          # keep | merge | discard | edit
    payload = Column(JSON, nullable=False)                    # action-specific args
    summary = Column(Text, nullable=False)                    # human-facing one-liner
    rationale = Column(Text, nullable=False)                  # reviewer's reasoning
    confidence = Column(Float, nullable=True)                 # 0..1, reviewer-agent only
    status = Column(String(16), nullable=False, index=True)   # pending | accepted | rejected | expired | superseded
    decided_at = Column(Float, nullable=True)
    decided_by = Column(String(64), nullable=True)
    decision_audit_id = Column(String(36), nullable=True)     # FK to audit_event.id
```

`action` enum on `AuditEvent`:

- `edit-frontmatter` — frontmatter replaced, body unchanged.
- `edit-body` — body replaced, frontmatter unchanged.
- `edit-full` — both in one save.
- `triage-keep` — queue candidate promoted to `/catalog/`.
- `triage-merge` — queue candidate merged into an existing catalog asset.
- `triage-discard` — queue candidate deleted.
- `create-asset` — new catalog asset created directly via the UI.
- `archive` — `status: archived` applied (already what Phase 6 pass 4
  does on its own; the UI surfaces it through this action so the audit
  log is complete).

### 2. Write service

```
web/apps/api/writes/
  __init__.py
  fs.py            # safe file I/O (path validation, atomic write)
  git.py           # subprocess wrapper: add, commit, status, log
  triage.py        # queue-candidate triage primitives (keep/merge/discard)
  editor.py        # frontmatter + body save primitives
  audit.py         # pending -> committed/failed transitions
  serialize.py     # frontmatter dict -> YAML text (preserves order, comments lost)
```

Critical contracts:

- `fs.py.safe_path(repo_root, rel)` — refuses anything outside
  `repo_root`, refuses symlinks, refuses paths with `..`. All writes go
  through it.
- `git.py.commit(repo_root, *, paths, message, author=...)` — single
  subprocess call, no shell. Author is configurable but defaults to
  `autoclaude-operator <operator@local>`. Returns the SHA.
- `audit.py.with_audit(intent) -> ctx` — context manager that creates
  the pending row on enter and finalises it on exit. Exceptions
  finalise as `failed` with the traceback.

### 3. Write flow

```
PUT /catalog/{slug}     (body: { frontmatter: {...}, body: "...", if_match: "<hash>" })

  1. Resolve slug -> DB row. 404 if missing.
  2. Compare row.version to if_match. 409 if mismatch (attach current row).
  3. Begin audit (status: pending; intent = request body).
  4. serialize.frontmatter_to_yaml(...) -> new file text.
  5. fs.atomic_write(path, text).
  6. git.commit(paths=[path], message=f"web: edit {bucket}/{slug}").
  7. Finalise audit (status: committed; result = {sha}).
  8. cache.sync()  (cheap; idempotent).
  9. 200 with the new row + version.
```

`atomic_write` uses `os.rename` semantics: write to `<path>.tmp`, then
rename. Crash between (5) and (6) leaves a written file with no commit
— the next `git status` shows it; a sweeper on next API start logs the
delta and offers a one-click "discard or commit" via the UI.

### 4. Triage actions

```
POST /queue/{slug}/triage    (body: { action, target_slug?, notes?, if_match })

action = "keep":
  - rename scout/queue/<slug>.md -> catalog/<slug>.md
  - flip frontmatter status: draft -> reviewed
  - bump updated_at to today
  - commit message: "web: triage keep <slug> -> catalog"

action = "merge":
  - read target catalog asset (catalog/<target_slug>.md)
  - append the candidate's body as "## From queue (<date>)\n..." section
  - if candidate.source.url is fresh, push it to target.source.alternates
  - delete scout/queue/<slug>.md
  - commit message: "web: triage merge <slug> -> <target_slug>"

action = "discard":
  - delete scout/queue/<slug>.md
  - notes field is required (forces operator to explain why)
  - commit message: "web: triage discard <slug>"

Every action records to AuditEvent. If a Proposal row referenced this
queue item, mark it `accepted` (keep/merge) or `rejected` (discard) and
write `decided_*` columns.
```

### 5. Proposal endpoints

```
GET  /proposals?status=pending&source=reviewer-agent&target_bucket=queue
GET  /proposals/{id}
POST /proposals/{id}/accept   (body: { if_match?: "<proposal version>" })
POST /proposals/{id}/reject   (body: { notes: "..." })
DELETE /proposals/{id}        # rare; usually transitions to a status instead
```

`accept` translates the proposal into a triage call (the proposal's
`payload` matches the triage shape) and runs it. The audit row links back
to the proposal id.

Operators can also create their own draft proposals (`source: operator`)
— useful for parking a decision for later or sharing intent across
sessions. v1 ships the data path; the UI may not expose this until 8.4+.

### 6. UI

Routes added to `/web/apps/web/app/`:

- `catalog/[slug]/edit/page.tsx` — frontmatter form + body editor + save.
- `queue/[slug]/page.tsx` — extended with a triage action panel + the
  pending proposals list.
- `proposals/page.tsx` — operator inbox: pending proposals across all
  buckets, sortable by confidence and creation time.

Components added to `/web/apps/web/components/`:

- `FrontmatterForm.tsx` — schema-aware form. Renders the asset.schema
  fields, validates with zod.
- `BodyEditor.tsx` — textarea + react-markdown preview, side-by-side.
- `TriagePanel.tsx` — three buttons, notes field, version-mismatch
  banner.
- `ProposalCard.tsx` — proposal summary + accept/reject controls.

Optimistic UI: actions show a spinner and re-fetch the row on success.
On 409 the form pulls the new row and shows a "this changed since you
opened it" banner with a diff view (rendered with `react-markdown` over
two columns).

### 7. Failure modes & required handling

| Failure                                                  | Action                                                                  |
| -------------------------------------------------------- | ----------------------------------------------------------------------- |
| Working tree dirty before a save                         | Refuse the save; surface the dirty paths; ask operator to commit or stash. The UI never auto-stashes. |
| git commit fails (e.g. pre-commit hook)                  | Audit row finalised as `failed`; file rolled back via `git checkout -- <path>`; 422 with hook output. |
| Two saves race for the same file                         | `_WRITE_LOCK` (process-wide) serialises. First wins; second gets 409 on its If-Match. |
| Schema validation fails                                  | 422 with the pydantic detail. No file write, no audit row (only validation, not intent). |
| Symlink in target path                                   | Refuse with 400. `fs.safe_path` rejects symlinks defensively. |
| Crash between write and commit                           | Sweeper on next API start logs "<n> uncommitted files since last sync" and surfaces them in `/health`'s `warnings` field. Operator decides via `proposals/orphans` UI (or just runs `git status` and commits/discards by hand). |
| Reviewer-agent proposal references a queue item that's been triaged | Mark the proposal `superseded` on the next /sync. UI hides superseded proposals by default. |

### 8. Tests

Unit:

```
tests/unit/web/
  test_writes_fs.py         atomic_write, safe_path, symlink refusal
  test_writes_git.py        subprocess wrapper: add/commit/log; failure paths
  test_writes_audit.py      pending -> committed transitions; rollback on raise
  test_writes_serialize.py  frontmatter dict <-> YAML round trip
```

Integration (these need a real `git init` repo as the fixture):

```
tests/integration/web/
  test_write_back_edit.py        PUT /catalog/{slug} happy path -> commit lands
  test_write_back_409.py         stale If-Match -> 409 + current row
  test_write_back_triage.py      keep/merge/discard end-to-end
  test_write_back_dirty_tree.py  refuses save with uncommitted changes
  test_proposal_lifecycle.py     create -> accept -> audit -> file change
```

### 9. Code surface

```
web/apps/api/writes/              new
web/apps/api/routers/writes.py    new — register the write endpoints
web/apps/api/routers/proposals.py new — proposal CRUD
web/apps/api/db/models.py         + Asset.version, AuditEvent, Proposal
web/migrations/versions/0002_writes.py    new — add tables + column
web/apps/web/app/catalog/[slug]/edit/page.tsx   new
web/apps/web/app/queue/[slug]/page.tsx          extended
web/apps/web/app/proposals/page.tsx             new
web/apps/web/components/...                     new components (see § 6)
web/apps/web/lib/api-types.ts                   + AuditEvent, Proposal types
web/apps/web/lib/api.ts                         + writes / proposals helpers
```

## Open questions to resolve during the session

1. **Where does the git author come from?** Env var
   `AUTOCLAUDE_GIT_AUTHOR_NAME` / `_EMAIL`, falling back to
   `git config user.name`/`user.email`? *Recommendation: try git config
   first (matches the operator's existing identity), env-var override
   if set. Refuse to write if neither is configured.*
2. **Do we use `git commit --no-verify` to skip pre-commit hooks?**
   *Recommendation: never. Hook failures are the operator's signal that
   something's wrong; we surface them and refuse the write.*
3. **Should `triage keep` always promote to `catalog`, or can it route to
   `claude/<area>` for adopted items?** *Recommendation: catalog only in
   8.3. `status: adopted` triggers a separate "copy to /claude/" flow
   later — multi-target writes complicate the audit story.*
4. **Soft-delete vs hard-delete for `discard`?** *Recommendation: hard
   delete. The audit row preserves the intent + the candidate's full
   payload in `intent.snapshot`. Git history has the file too.*
5. **Where does the proposal-supersede sweep run?** *Recommendation: at
   the tail of every `CachedIndex.sync()`. Cheap; runs every 60s; matches
   how Phase 6 dedup integrates into runner.run_once.*

## Task breakdown

| #  | Task                                                                                              | Notes                                  |
| -- | ------------------------------------------------------------------------------------------------- | -------------------------------------- |
| 1  | Migration `0002_writes.py`: add `asset.version`, `audit_event`, `proposal` tables.                | SQLite + Postgres compatible.          |
| 2  | `web/apps/api/db/models.py` updates; query helpers in `db/query.py`.                              | Backfill `version = content_hash`.     |
| 3  | `web/apps/api/writes/fs.py` (safe_path + atomic_write) + tests.                                   |                                        |
| 4  | `web/apps/api/writes/git.py` (subprocess wrapper) + tests.                                        |                                        |
| 5  | `web/apps/api/writes/serialize.py` (frontmatter ↔ YAML; preserves block style) + tests.           |                                        |
| 6  | `web/apps/api/writes/audit.py` (pending → committed/failed) + tests.                              |                                        |
| 7  | `web/apps/api/writes/editor.py` + `triage.py` (the two action verbs).                             |                                        |
| 8  | `routers/writes.py` (`PUT /catalog/{slug}`, `POST /queue/{slug}/triage`).                         |                                        |
| 9  | `routers/proposals.py` (`GET /proposals`, `POST /proposals/{id}/accept|reject`).                  |                                        |
| 10 | Sync-tail sweep: mark superseded proposals; surface orphan working-tree changes in `/health`.     |                                        |
| 11 | Pydantic API models for the new shapes; mirror in `api-types.ts`.                                 |                                        |
| 12 | Integration tests against a `git init` fixture under `tmp_path`.                                  |                                        |
| 13 | Frontend: `FrontmatterForm`, `BodyEditor`, `TriagePanel`, `ProposalCard` components.              |                                        |
| 14 | Frontend pages: `catalog/[slug]/edit`, extended queue detail, `proposals/`.                       |                                        |
| 15 | `/conventions/web-app.md` update: write-back flow, optimistic lock, sweeper invariant.            |                                        |
| 16 | `/command-center/runbooks/web-app.md`: new env vars (`AUTOCLAUDE_GIT_*`), troubleshooting.        | Bump `last_verified`.                  |
| 17 | Quality gate + manual smoke (full edit + commit roundtrip in browser).                            |                                        |
| 18 | Commit. Mark plan `status: done`.                                                                  |                                        |

## Quality gate (must all pass before commit)

```sh
uv run ruff check scout/ web/ tests/ tools/
uv run pytest -q
uv run pytest tests/integration/web -q

# Smoke (manual)
rm -rf web/.data && uv run autoclaude-index upgrade
uv run autoclaude-api &
# In a real git checkout, hit PUT /catalog/{slug} with a small frontmatter edit;
# confirm `git log -1 -- catalog/{slug}.md` shows the new commit; confirm
# /catalog/{slug} reflects the change; confirm /audit?target_path=... lists
# the event.
kill %1
```

## Atomicity check (REQUIRED for 8.3)

- A save that succeeds writes both the file and the commit. `git log -1`
  references the changed file.
- A save that fails after writing the file but before committing leaves
  the working tree dirty. The sweeper logs it; `/health` surfaces it as a
  warning; no audit row remains in `pending` longer than one sync cycle
  (60s) without becoming `failed`.
- Two concurrent saves on the same path: the second returns 409. The
  first wins. The DB / file system never end up disagreeing.

## When this plan becomes stale

`status: active` while 8.3 implementation is in flight. Flips to `done`
when the commit lands and the smoke passes. If a follow-up milestone
fundamentally changes the write path (e.g. moving to a branch + PR
workflow), that milestone gets a new plan with
`supersedes: [phase-8-3-write-back]`.
