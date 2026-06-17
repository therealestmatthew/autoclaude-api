---
name: phase-8-web-command-center
title: "Phase 8 — Web command center"
phase: 8
status: active
created_at: 2026-06-16
updated_at: 2026-06-16
completed_at:
supersedes: []
superseded_by:
locked_decisions:
  - "Markdown remains canonical. The web app is a *view* over the repo, not a replacement for it. Any DB the web app uses is a *derived index*, rebuildable from `git ls-files` at any time. Git is still the database."
  - "Local-first by default. The full v1 stack (FastAPI + Next.js + index) runs on `localhost` with `uv run` and `npm run dev` — no Docker, no cloud account, no auth required. Cloud deploy is a separate milestone (8.5)."
  - "Top-level `/web/` directory. Backend (`apps/api/`) and frontend (`apps/web/`) sit side-by-side. The Python backend is part of the existing `autoclaude` package; the frontend is a standalone npm project."
  - "Backend = FastAPI on the existing Python 3.11 + pydantic + httpx stack. No new language runtime introduced unless a frontend explicitly requires it."
  - "Frontend = Next.js 15 (App Router) + TypeScript + Tailwind v3 + shadcn/ui. Picked over Astro / SvelteKit because the SSR + RSC + route handler combo gives us a path to streaming, auth (Supabase Auth), and serverless deploy without a rewrite."
  - "v1 ships read-only. The web app does not write to markdown files until 8.3. Editing flows surface as 'open in editor' links + manual commit; the heavy lift (typed editor + git commit pipeline + audit log) is its own milestone."
  - "v1 index is in-memory (Python dict keyed by slug, populated from a single repo walk on cold start, invalidated by mtime). DB-backed index (SQLite default, Postgres-compatible via SQLAlchemy) lands in 8.2 when we have a concrete need for persistence (write-back audit log, multi-process serving, or repo grows past ~5k assets)."
  - "Process tax is paid up front. Phase 8 lands `/conventions/web-app.md` (architectural rules), `/command-center/runbooks/web-app.md` (operator runbook), and a maintenance section in this plan. New surfaces follow the same convention or push back."
  - "The Python backend uses the existing pyproject groups. `[project.optional-dependencies]` group `web` (or PEP 735 group `web`) holds FastAPI + uvicorn so a slim install (`uv sync --no-dev`) without the web group still works for headless scout usage."
---

# Phase 8 — Web command center

## Goal

Stand up a web app that lets the operator browse and reason about the entire repo's state without grepping markdown by hand. Catalog, queue, threads, engagements, conventions, plans — all queryable, filterable, linkable in a browser.

The web app is the third surface, complementing:

- `/scout/` (ingest pipeline — CLI)
- `/command-center/` (markdown rollups — CLI + git)
- `/web/` (operator UI — browser) ← Phase 8

The goal of v1 is **comprehension at a glance**: an operator who opens `localhost:3000` can see what's in the catalog, what's in the queue, what the scout did this week, and which engagements are active. Edit flows are intentionally out of scope for v1 so we ship the read layer right before we layer on writes.

## Non-goals (out of scope for this phase)

- **Replacing markdown.** The repo stays markdown-first. The web app reads markdown.
- **Write-back to markdown.** Editing assets through the UI and producing git commits is milestone 8.3, not v1.
- **Authentication.** Single-operator local-first. Multi-user / cloud auth is 8.5.
- **Real-time agents in the browser.** Running scout / dedup / extractors from the UI is later.
- **Replacing `/conventions/` lookup with web navigation.** Conventions stay the source of truth; the web app links to them, doesn't rewrite them.
- **A heavy state-management framework.** Server Components + simple fetch is enough; we'll add Redux/Zustand only when client state demands it.

## Constraints (inherited and new)

Inherited from prior phases:

- **Markdown + YAML frontmatter is canonical.** The web app reads files; it doesn't invent a new representation.
- **Schema lives in `/catalog/_schema/asset.schema.md` and `/conventions/frontmatter.md`.** The web app's typed models mirror those — when they drift, the schema is authoritative.
- **Provenance is required on every catalog asset.** The web app surfaces `source.*` and `discovered.*` prominently.
- **Threads are append-only JSONL at `/command-center/threads/`.** The web app reads, never writes.

New for Phase 8:

- **No persistent state in `/web/`.** Build artifacts (`.next/`, `node_modules/`, `__pycache__/`) are gitignored. The index lives in memory in v1.
- **API surface is typed.** Pydantic models on the wire; the frontend has a generated `lib/api-types.ts` (or hand-written if generation is more friction than it's worth in v1).
- **Determinism in displays.** A list of catalog assets sorted by `updated_at desc` is reproducible — no random fallback ordering.

## Design

### 1. Directory layout

```
/web/
  README.md                       what /web/ is, how to run it
  apps/
    api/                          FastAPI backend (Python, part of autoclaude package)
      __init__.py
      main.py                     FastAPI app factory + CORS
      settings.py                 env-driven config (repo root, port, log level)
      indexer.py                  repo walker → typed AssetRecord
      models.py                   Pydantic API models (separate from indexer dataclasses)
      cache.py                    in-memory cache with mtime invalidation
      routers/
        __init__.py
        catalog.py
        queue.py
        threads.py
        engagements.py
        stats.py
        search.py
        conventions.py
        plans.py
    web/                          Next.js 15 frontend (TypeScript)
      package.json
      next.config.mjs
      tsconfig.json
      tailwind.config.ts
      postcss.config.js
      .env.example
      app/                        App Router routes
        layout.tsx                global shell (sidebar + content)
        page.tsx                  redirects to /dashboard
        dashboard/page.tsx
        catalog/page.tsx
        catalog/[slug]/page.tsx
        queue/page.tsx
        queue/[slug]/page.tsx
        engagements/page.tsx
        engagements/[slug]/page.tsx
        conventions/page.tsx
        plans/page.tsx
        threads/page.tsx
      components/
        Sidebar.tsx
        AssetCard.tsx
        AssetDetail.tsx
        StatCard.tsx
        ThreadEventRow.tsx
        QueueRow.tsx
      lib/
        api.ts                    typed fetcher
        api-types.ts              shapes mirroring Pydantic models
        format.ts                 date / status formatting helpers
```

The `/web/apps/api/` directory is part of the existing `autoclaude` Python package — same venv, same pyproject, same lint config. The `/web/apps/web/` directory is an isolated npm project; its dependencies do not touch the Python side.

### 2. Indexer (the linchpin)

A pure Python module that walks the repo and emits a typed record per markdown document. Reuses `scout._util.parse_frontmatter` so the parsing logic is shared.

```python
# web/apps/api/indexer.py

@dataclass(frozen=True)
class AssetRecord:
    path: str                # repo-relative POSIX path
    bucket: Bucket           # catalog | queue | engagement | convention | plan | runbook | readme | other
    slug: str                # name field, or filename stem if missing
    kind: str | None         # catalog kind, or None
    title: str | None
    status: str | None
    quality: int | None
    tags: tuple[str, ...]
    source: dict | None
    discovered: dict | None
    relations: dict | None
    created_at: str | None
    updated_at: str | None
    body: str                # markdown body below frontmatter
    issues: tuple[str, ...]  # parse / required-field issues (informational)
    mtime: float             # for cache invalidation


class Indexer:
    def __init__(self, repo_root: Path): ...
    def scan(self) -> list[AssetRecord]: ...
    def by_slug(self) -> dict[str, AssetRecord]: ...
    def by_bucket(self) -> dict[Bucket, list[AssetRecord]]: ...
    def stats(self) -> IndexStats: ...
```

Bucket classification by path:

| Path pattern                                                     | Bucket        |
| ---------------------------------------------------------------- | ------------- |
| `catalog/*.md` (excluding `_schema/`, `_examples/`, READMEs)     | `catalog`     |
| `scout/queue/*.md` (excluding `_template.md`, README)            | `queue`       |
| `consulting/engagements/<slug>/README.md`                        | `engagement`  |
| `conventions/*.md`                                               | `convention`  |
| `docs/plans/**/*.md` (excluding READMEs and session_prompts)     | `plan`        |
| `docs/runbooks/*.md` or `command-center/runbooks/*.md`           | `runbook`     |
| `**/README.md`                                                   | `readme`      |
| everything else with frontmatter                                 | `other`       |

Files that don't parse are still indexed with the parse error in `issues`. The web app shows a "needs frontmatter" badge so the operator can see the punch list.

Thread events are read separately via a `ThreadReader` that streams `/command-center/threads/*.jsonl`. The reader honors a date range and a limit, never loads more than N MB into memory.

### 3. Cache strategy

v1 uses an in-process `CachedIndex` wrapping `Indexer`:

- Cold start: walk the repo, build the index. (~100 files, <100ms on the current repo.)
- Subsequent requests: check mtime of the slowest-to-walk surfaces (`catalog/`, `scout/queue/`, `consulting/engagements/`). If any is newer than the cached snapshot, rebuild.
- Manual `POST /sync` endpoint forces rebuild (useful when `scout run` lands new queue files mid-session).

In 8.2 this gets replaced by SQLAlchemy + SQLite (default) / Postgres (cloud). The `Indexer` API stays the same; the storage swaps underneath.

### 4. API surface (v1, read-only)

| Method | Path                              | Returns                                              |
| ------ | --------------------------------- | ---------------------------------------------------- |
| `GET`  | `/health`                         | `{ok: true, version, repo_root}`                     |
| `GET`  | `/stats`                          | counts by kind / status / bucket; recent activity    |
| `GET`  | `/catalog`                        | list catalog assets; filters: kind, status, tag, q   |
| `GET`  | `/catalog/{slug}`                 | single asset with body + computed relations          |
| `GET`  | `/queue`                          | list queue candidates; filters: kind, q, since       |
| `GET`  | `/queue/{slug}`                   | single queue candidate                               |
| `GET`  | `/threads`                        | thread events; filters: date, agent, outcome, limit  |
| `GET`  | `/threads/recent`                 | last N events across all dates                       |
| `GET`  | `/engagements`                    | engagement roots                                     |
| `GET`  | `/engagements/{slug}`             | single engagement + nested files                     |
| `GET`  | `/conventions`                    | convention docs                                      |
| `GET`  | `/plans`                          | phase plans                                          |
| `GET`  | `/search?q=...`                   | cross-bucket fuzzy search (slug, title, tags, body)  |
| `POST` | `/sync`                           | force reindex; returns new stats                     |

All responses are JSON, all sortable lists default to `updated_at desc`. Validation errors return 4xx with a structured Pydantic detail.

### 5. Frontend surfaces (v1)

| Route                       | Purpose                                                                       |
| --------------------------- | ----------------------------------------------------------------------------- |
| `/dashboard`                | Counts (catalog, queue, threads); recent activity; punch list of `issues`     |
| `/catalog`                  | Asset browser with filter sidebar (kind / status / tag); sortable, paginated  |
| `/catalog/[slug]`           | Asset detail: frontmatter pretty-printed; rendered body; relations graph link |
| `/queue`                    | Queue candidate triage list: kind, source, discovered date, suggested action  |
| `/queue/[slug]`             | Candidate detail: source link, body preview, "open in editor" deep link       |
| `/engagements`              | List of engagement roots with status + client                                 |
| `/engagements/[slug]`       | Engagement detail: status, scoping, retro, status reports                     |
| `/conventions` / `/plans`   | Navigable convention / plan index; click-through to body                      |
| `/threads`                  | Thread event timeline with date picker and agent / outcome filter             |

Server Components do the data fetching (calls to FastAPI happen server-side via `lib/api.ts`). Interactive bits (filter inputs, search box) are client components.

Styling: Tailwind v3 + shadcn/ui primitives (Card, Button, Input, Badge, Tabs, Separator). Dark mode supported but defaulted to system preference.

### 6. Failure modes & required handling

| Failure                                                  | Action                                                                  |
| -------------------------------------------------------- | ----------------------------------------------------------------------- |
| Repo root env var unset                                  | API exits with a clear error on startup; runbook explains the fix       |
| Markdown file with malformed frontmatter                 | Indexed with `issues: ["malformed-frontmatter"]`; UI shows a warning    |
| Thread JSONL file with a bad line                        | Skip the line; record an `issues` entry on the day's record             |
| Queue / threads directory missing (fresh checkout)       | Empty results; no error                                                 |
| Concurrent file change during a request                  | Cache invalidates on next mtime check; current request returns last     |
| Frontend can't reach API                                 | UI shows a clear "API down" banner with the configured URL              |

### 7. Tests

```
tests/unit/web/
  test_indexer.py             bucket classification, slug fallback, mtime
  test_cache.py               cold start, hit, mtime-invalidate, force-sync
  test_api_models.py          Pydantic round-trip vs indexer output

tests/integration/web/
  test_api_catalog.py         spin up FastAPI test client; query the fixtures
  test_api_queue.py
  test_api_threads.py         JSONL fixture → /threads response
  test_api_search.py
```

Fixtures land under `tests/fixtures/web/` with a miniature catalog (3 assets), a queue (2 candidates), a thread log (1 day, 4 events), and a single engagement. The integration tests construct a temp repo from fixtures via the existing `scout_world` pattern.

Frontend tests are deferred to a follow-up (Playwright + a single smoke route) — the foundation lands without them because the page logic is thin Server Component glue.

### 8. Code surface (rough)

```
web/                               new
  README.md
  apps/api/                        new (Python; part of autoclaude package)
  apps/web/                        new (Next.js)
tools/web.py                       new — `uv run autoclaude-api` entrypoint
conventions/web-app.md             new
command-center/runbooks/web-app.md new
docs/plans/phase-8-web-command-center.md  (this file)
pyproject.toml                     + `web` dep group; + script entry
CLAUDE.md                          + `/web/` row in directory layout
.gitignore                         + node_modules, .next, .env.local under web/
```

## Open questions to resolve during the session

1. **Where do generated TypeScript types live?** Auto-generate from FastAPI's OpenAPI? Hand-maintain a mirror file? *Recommendation: hand-maintain `lib/api-types.ts` in v1. Code-gen (openapi-typescript) is a 9.x concern once the API surface stabilizes.*
2. **Frontend package manager.** npm / pnpm / bun? *Recommendation: npm. Lowest barrier; matches what most operators have installed.*
3. **shadcn/ui or build primitives from scratch?** *Recommendation: shadcn/ui. It generates copy-pasted components we own (no opaque dependency), and gives us a Radix-quality baseline.*
4. **Markdown rendering in the browser.** react-markdown + rehype, or server-render via Python `markdown` package and ship HTML? *Recommendation: react-markdown + rehype-highlight on the client. Avoids a Python markdown dep and lets us style with Tailwind prose.*
5. **Should the indexer also surface assets in `/claude/` (agents, skills, plugins) as a separate bucket?** *Recommendation: yes — add `claude` bucket in v1, since they share the catalog asset schema. Surface them under a 'Toolkit' nav section.*

Each question gets answered as the work lands; resolved decisions move into `locked_decisions:` at phase close.

## Task breakdown (suggested execution order)

| #  | Task                                                                                          | Parallelizable with |
| -- | --------------------------------------------------------------------------------------------- | ------------------- |
| 1  | Land this plan (frontmatter + body).                                                          | —                   |
| 2  | Scaffold `/web/` directory; add `.gitignore` entries; add `web` dep group to pyproject.toml.   | 1                   |
| 3  | Implement `web/apps/api/indexer.py` (pure walker, no FastAPI yet) + unit tests.               | 4 (after 2)         |
| 4  | Implement `web/apps/api/cache.py` (mtime-invalidating wrapper) + unit tests.                  | 3                   |
| 5  | Implement `web/apps/api/models.py` (Pydantic) + `main.py` (FastAPI app factory + CORS + /health). | 6                |
| 6  | Implement routers: catalog, queue, threads, engagements, stats, search, conventions, plans.   | 5                   |
| 7  | Integration tests against the fixture mini-repo.                                              | 8                   |
| 8  | Add `tools/web.py` + `autoclaude-api` script entry; document `uv run autoclaude-api`.         | 7                   |
| 9  | Scaffold Next.js app: package.json, tsconfig, tailwind, layout, sidebar, dashboard page.      | 10                  |
| 10 | Build Catalog browser + detail; Queue list + detail; Engagements; Threads; Conventions; Plans. | 9                  |
| 11 | Write `/conventions/web-app.md` + `/command-center/runbooks/web-app.md`.                      | 12                  |
| 12 | Update `CLAUDE.md`: add `/web/` row in layout; add v1 commands in commands section.           | 11                  |
| 13 | Quality gate: `uv run ruff check`, `uv run pytest`, manual smoke `uv run autoclaude-api` + `npm run dev`. | 14       |
| 14 | Commit as one logical change. Mark plan `status: done` only when 8.1 ships; otherwise leave `active`. |              |

## Quality gate (must all pass before commit)

```sh
uv run ruff check scout/ web/ tests/
uv run pytest -q
uv run pytest tests/integration -q
# Smoke (manual):
uv run autoclaude-api &        # FastAPI on :8000
curl http://localhost:8000/health        # {ok: true, ...}
curl http://localhost:8000/stats         # counts > 0
cd web/apps/web && npm install && npm run dev  # Next.js on :3000
# Browser: visit / and see the four nav surfaces populated.
```

## Milestones beyond v1 (8.x)

Each milestone is its own commit (and may warrant its own plan document if the scope grows):

| Milestone | Scope                                                                                                  |
| --------- | ------------------------------------------------------------------------------------------------------ |
| **8.1**   | Foundation. This plan. Read-only indexer + FastAPI + Next.js shell. ← THIS SESSION                     |
| **8.2**   | Persistent index. SQLAlchemy + SQLite default; Postgres-compatible. Alembic migrations. Sync command.  |
| **8.3**   | Write-back. Frontmatter editor; body editor; git commit pipeline with audit log; queue triage actions. |
| **8.4**   | Real-time. SSE / WebSocket thread tail; live scout-run telemetry; toast notifications.                 |
| **8.5**   | Cloud deploy. Supabase Auth + Postgres; Vercel for frontend; Fly.io / Railway for FastAPI; cron sync.  |
| **8.6**   | AI features. LLM-backed search; auto-merge proposals on queue items; reviewer agent surfaced in UI.    |

## Maintenance process (the part about "as it grows over time")

This phase isn't done when v1 ships — it's done when the *process* for keeping the web app maintainable is in place. The process:

1. **Every new surface follows `/conventions/web-app.md`.** A new route, a new section, a new component — they go in the documented places, with the documented frontmatter / typing / file layout. If the convention doesn't fit, the convention gets updated *before* the surface ships, not after.
2. **Schema changes flow from the catalog out.** Adding a `kind`, a `status` value, or a frontmatter field starts in `/catalog/_schema/asset.schema.md` and `/conventions/frontmatter.md`, propagates into `web/apps/api/models.py`, then to `web/apps/web/lib/api-types.ts`, then to the UI components that render it.
3. **Tests block regressions.** The indexer is covered by unit tests; every router has a happy-path integration test; new routes ship with a test in the same commit.
4. **Plan documents are kept forever.** This plan lives at `/docs/plans/phase-8-web-command-center.md`. Each subsequent milestone (8.2, 8.3, …) gets its own plan if its scope warrants — and it `supersedes` or `extends` this one in the frontmatter.
5. **The runbook is the operator's contract.** `/command-center/runbooks/web-app.md` documents how to start, stop, debug, and recover the web app. It gets a `last_verified` bump every time someone runs it end-to-end. A runbook older than 90 days without a verification touch is `status: stale`.
6. **Quarterly upgrade cadence.** Dependency upgrades (FastAPI, Next.js, Tailwind, shadcn, Python minor) happen on a single quarterly commit. Security patches happen immediately.
7. **Index is rebuildable, always.** No state lives in the index that isn't reproducible from the repo + git. If the index gets corrupted, deleting and rebuilding from `git ls-files` must restore full functionality. This is the invariant that lets us swap storage layers between milestones.

## Commit message (template for 8.1)

```
Phase 8.1: web command center — foundation

- /web/apps/api: FastAPI backend on the existing autoclaude package.
  Markdown indexer + in-memory cache + read-only routers for catalog,
  queue, threads, engagements, conventions, plans, stats, search.
- /web/apps/web: Next.js 15 + Tailwind + shadcn/ui frontend. Sidebar
  shell + four primary surfaces (catalog browser, queue review,
  command-center dashboard, engagement tracker).
- tools/web.py + `autoclaude-api` script: one-command backend start.
- /conventions/web-app.md: architectural rules for the web app —
  markdown is canonical, web is a derived view, how to add a surface.
- /command-center/runbooks/web-app.md: how to start, debug, and recover
  the web app.
- /docs/plans/phase-8-web-command-center.md: design + 8.x milestone
  roadmap + maintenance process.
- Tests: unit (indexer, cache, models) + integration (each router).
- CLAUDE.md, pyproject.toml, .gitignore: updated for the new surface.
```

## When this plan becomes stale

`status: active` while milestones 8.1 through 8.6 land. Each milestone either updates this plan's body (small scope) or spawns its own plan that `supersedes` or `extends` it (large scope). Status flips to `done` when 8.6 lands or when the web app is replaced by a fundamentally different design (in which case a successor plan `supersedes` this one).
