---
name: phase-8-web-command-center-prompt
title: "Session prompt — Phase 8 (web command center)"
kind: session-prompt
phase: 8
status: active
related: [phase-8-web-command-center]
created_at: 2026-06-16
updated_at: 2026-06-16
---

# Session prompt — Phase 8 (web command center)

Paste the block below as your opening message to a fresh Claude Code session
in `/code/autoclaude` when continuing Phase 8. The substantive plan is
canonical in-repo at `/docs/plans/phase-8-web-command-center.md`; this
prompt sequences the cold-start reads and pins the locked decisions.

Phase 8.1 (foundation: indexer + read-only FastAPI + Next.js shell + plan +
conventions + runbook + tests) is **already shipped**. This prompt is for
continuing into 8.2 and beyond.

---

```
We are continuing Phase 8 of the autoclaude repo. The full plan is in-repo at:

  /code/autoclaude/docs/plans/phase-8-web-command-center.md

Read that plan IN FULL before doing anything else. Pay specific attention
to the "Milestones beyond v1 (8.x)" table and the "Maintenance process"
section — the milestone you pick up next is constrained by both.

Then read these in order (all small, cold-start essentials):

  1. CLAUDE.md                                       (operating brief; note the /web/
                                                      layout row and the new commands)
  2. conventions/web-app.md                          (the 10 architectural rules — these
                                                      are the contract for any change to /web/)
  3. command-center/runbooks/web-app.md              (how the surface runs; bump
                                                      `last_verified` after you smoke it)
  4. conventions/frontmatter.md                      (schema authority — any new
                                                      frontmatter field starts here)
  5. catalog/_schema/asset.schema.md                 (the canonical asset shape the
                                                      API models mirror)
  6. web/README.md                                   (entry point to the /web/ tree)
  7. web/apps/api/indexer.py                         (the linchpin — read end-to-end)
  8. web/apps/api/cache.py                           (mtime invalidation contract)
  9. web/apps/api/main.py                            (app factory + router wiring)
  10. web/apps/api/models.py                         (wire format)
  11. web/apps/api/routers/_filters.py               (shared filter/sort/paginate
                                                      helpers — extend rather than
                                                      duplicate)
  12. web/apps/web/lib/api-types.ts                  (TS mirror of models.py — these
                                                      must stay in sync)
  13. web/apps/web/lib/api.ts                        (typed client used by every page)
  14. web/apps/web/app/layout.tsx + components/Sidebar.tsx
                                                     (the shell every new surface
                                                      plugs into)
  15. tests/unit/web/test_indexer.py
      + tests/integration/web/conftest.py            (the test pattern — fixture repo
                                                      copy + TestClient)
  16. docs/plans/phase-7-observability.md            (locked decisions about JSONL
                                                      thread shape + token-burn fields
                                                      — the threads router consumes
                                                      these; any change must respect them)

Then check working-tree state with `git status --short`. The tree should
be clean at the start of a new milestone — confirm before beginning, and
ask if it isn't.

ALSO look at:

  uv run autoclaude-api &                            # backend boots clean on :8000
  curl -s http://localhost:8000/health | jq          # ok: true; records > 0
  curl -s http://localhost:8000/stats | jq '.stats.by_bucket'   # sane counts
  kill %1                                            # stop the backend
  ls web/apps/web/node_modules 2>/dev/null || echo "frontend deps not installed"

Locked decisions from Phase 8.1 (do NOT relitigate — see the plan's
`locked_decisions:` for the canonical list and rationale):

- Markdown remains canonical. Any DB is a derived, rebuildable index.
- Local-first by default. No Docker / cloud account / auth required for
  v1 surfaces. Cloud deploy is milestone 8.5, not now.
- Top-level /web/ directory with apps/api (Python, part of the autoclaude
  package) + apps/web (standalone Next.js). The two deploy independently.
- Backend = FastAPI on the existing pydantic / httpx stack.
- Frontend = Next.js 15 (App Router) + TypeScript + Tailwind v3 + lucide
  + react-markdown. No state-management framework, no styled-components.
- Routers do NO I/O. The CachedIndex (8.1) or its persistent successor
  (8.2+) is the only thing that touches the filesystem or DB.
- The API surface is typed end to end. Pydantic on the wire; a hand-
  maintained TS mirror in web/apps/web/lib/api-types.ts. Code-gen is
  deferred until the API stabilizes.
- Schema changes start in /catalog/_schema/asset.schema.md and
  /conventions/frontmatter.md, then propagate to web/apps/api/models.py,
  then to api-types.ts, then to UI. Never reverse the order.
- Every new surface follows /conventions/web-app.md § "Adding a new
  surface". Every router PR ships with a test in the same commit.

Pick ONE of these milestones to execute this session. They are listed in
the order the plan recommends; do not interleave.

  Milestone 8.2 — Persistent index
    Replace the in-memory CachedIndex with SQLAlchemy + SQLite (default)
    and Postgres-compatible models. Add Alembic migrations under
    web/migrations/. Add `autoclaude-index sync` CLI command. The
    Indexer.scan() result drains into the DB; routers read from the DB.
    Indexer.scan() stays pure and remains the source of truth for the
    schema. SQLAlchemy must NOT replace the pydantic API models.

  Milestone 8.3 — Write-back
    Frontmatter editor (form-driven, validated against the schema). Body
    editor (textarea + preview). Git commit pipeline with an audit log
    in /command-center/threads/. Queue triage actions (keep / merge /
    discard). Requires 8.2 for the audit log persistence.

  Milestone 8.4 — Real-time thread tail
    SSE endpoint at /threads/stream. Frontend hook that appends to the
    dashboard's recent-events list as new JSONL lines land. No
    WebSockets — SSE is enough and survives proxies cleanly.

  Milestone 8.5 — Cloud deploy
    Supabase Auth (uses the already-adopted plugin/skill in /catalog/).
    Vercel for frontend; Fly.io OR Railway for FastAPI (decide and lock
    in the milestone's plan). Cron-driven sync from a deploy that
    re-clones the repo on a schedule. Requires 8.2 for the DB and 8.3
    for write-back to be meaningful in production.

  Milestone 8.6 — AI features
    LLM-backed semantic search (pgvector embeddings). Auto-merge
    proposals on queue items (consumes Phase 6 dedup output). Reviewer
    agent surfaced in the UI. Requires 8.2 (DB) and 8.5 (auth/secret
    store).

If you are picking up 8.2 (the recommended next), write a milestone plan
at /docs/plans/phase-8-2-persistent-index.md that `supersedes: []` and
EXTENDS phase-8-web-command-center (set its frontmatter `related: ...`).
The milestone plan answers these open questions before any code lands:

  Q1. SQLite-only for 8.2, or SQLite-default-with-Postgres-via-DSN?
      Recommendation: same schema for both, default DSN = SQLite,
      override via env var. Alembic migrations target both dialects.
  Q2. Where does the SQLite file live?
      Recommendation: web/.data/index.sqlite (gitignored). Never in
      the repo root.
  Q3. Sync triggers: manual (POST /sync) only, or also a file watcher?
      Recommendation: manual + a polling reconciler (every 60s) for
      8.2; a real watcher (`watchfiles`) lands in 8.3 when writes need
      to invalidate on the same machine.
  Q4. Schema versioning: do we keep the indexer dataclasses and add
      SQLAlchemy models, or unify into SQLModel?
      Recommendation: keep them separate. Indexer is pure / domain;
      SQLAlchemy models are storage. The conversion lives next to the
      storage code.

Quality gate before commit (must all pass):

  uv run ruff check scout/ web/ tests/
  uv run pytest -q
  uv run pytest tests/integration -q
  uv run pytest tests/unit/web tests/integration/web -q
  # Smoke (manual):
  uv run autoclaude-api &
  curl -s http://localhost:8000/health
  curl -s http://localhost:8000/stats
  # For 8.2 specifically, also:
  uv run autoclaude-index sync     # populates the DB; idempotent on rerun
  sqlite3 web/.data/index.sqlite "select count(*) from asset"

Idempotency check (REQUIRED for 8.2):

- Run `uv run autoclaude-index sync` twice; the second invocation must
  NOT produce a row diff (upserts only on actual content change).
- Killing the backend mid-sync must leave the DB in a recoverable state.
  A subsequent sync converges to the correct snapshot.

Commit as ONE logical change per milestone. Do not bundle 8.2 and 8.3.

Out of scope for this session (do not start unless you picked it as the
milestone above):

- Authentication, sessions, or any multi-user concern (8.5).
- Write-back to markdown / git commits from the UI (8.3).
- Real-time / SSE / WebSocket transport (8.4).
- Vector embeddings, LLM-backed search, reviewer agents (8.6).
- Renaming any of the 8.1 directories or top-level scripts. The 8.1
  layout is the contract /conventions/web-app.md enforces.

When done, summarize: which milestone, tests passing count, ruff status,
smoke results (health + stats counts, plus milestone-specific smokes),
idempotency check results (if applicable), the resolution of any open
questions the milestone plan called out, the commit SHA, and any rough
edges. If 8.2 landed, ALSO bump
/command-center/runbooks/web-app.md's `last_verified` to today.

Then mark the milestone plan `status: done`, set `completed_at`, finalise
its `locked_decisions:`, and (if you were on 8.6, the last milestone)
flip phase-8-web-command-center to `status: done` as well — otherwise
leave it `active`.
```

---

## Why this prompt is shaped this way

- **Milestone menu, not a single forced path.** Phase 8 is a long phase
  with five follow-on milestones (8.2–8.6). A fresh session shouldn't
  have to guess which one is next; it should be told the order, the
  prerequisites, and what to write before code lands. Each milestone is
  its own logical commit.
- **Locked decisions copied inline, not just linked.** A new session
  often skims the plan but reads the prompt twice. The decisions that
  most need defending against "tidiness" instincts (markdown is
  canonical, routers do no I/O, the indexer stays pure even when SQLAlchemy
  arrives) live verbatim here so they survive context compaction.
- **The reading order is dependency-ordered.** A new session that
  modifies the DB layer in 8.2 without first reading `indexer.py` and
  the cache contract will produce a parallel schema that drifts.
  Listing the read order forces the conversion path: indexer → cache →
  models → router → frontend type, never reverse.
- **Open questions for 8.2 named upfront.** SQLite vs Postgres default,
  where the SQLite file lives, sync trigger model, ORM strategy — these
  decisions have second-order effects on 8.3+. Solving them at the top
  of the session beats solving them under tactical pressure mid-PR.
- **Idempotency is a milestone-specific gate.** A persistent index that
  isn't idempotent on rerun is worse than no index — it accumulates
  drift silently. Calling out idempotency at the quality-gate level
  prevents declaring victory on a one-shot success.

## When this file becomes stale

This prompt stays `status: active` while Phase 8 milestones are
incomplete. Each milestone that ships bumps `updated_at` on this prompt
to reflect the new "next milestone" framing. When Phase 8.6 (the final
milestone) lands and `phase-8-web-command-center.md` flips to
`status: done`, rename this file to `phase-8-web-command-center.done.md`.
