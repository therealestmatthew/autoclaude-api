---
name: convention-web-app
title: "Convention — Web app architecture"
kind: convention
status: active
created_at: 2026-06-16
updated_at: 2026-06-16
---

# Convention — Web app architecture

The rules that govern the Phase 8 web command center at `/web/`. These rules exist so the web app stays maintainable as new surfaces and contributors arrive.

If you find yourself wanting to break one of these rules, update the convention first (in the same change) or push back. The convention is the contract.

## 1. Markdown is canonical

The web app is a **view** over the repo. It does not own data. Anything the API returns must be reproducible by walking `git ls-files`.

- The index lives in memory in v1 and (later) in SQLite/Postgres. Either way, deleting the index and rebuilding from the repo must restore full functionality.
- No write path in v1. When write-back lands (milestone 8.3), writes produce both a file change and a git commit — never a DB-only mutation.
- New frontmatter fields land in `/catalog/_schema/asset.schema.md` and `/conventions/frontmatter.md` **first**, then propagate into the API models. Never the other way around.

## 2. Two apps, side by side

The backend (`/web/apps/api/`) and frontend (`/web/apps/web/`) deploy independently. Implications:

- The backend serves JSON over HTTP. No server-rendering of UI from Python.
- The frontend has zero Python dependencies. It talks to the backend via a typed client at `lib/api.ts`.
- A new surface adds an API endpoint **and** a frontend page — never one without the other.
- Cross-cutting concerns (auth, logging, telemetry) live on the backend; the frontend is intentionally thin.

## 3. The Python backend is part of the `autoclaude` package

`web/apps/api/` is Python code. It uses the existing venv, the existing pyproject, the existing ruff config. It is not a separate package.

- Imports from `scout.*` are fine (and encouraged — `scout._util.parse_frontmatter` is the shared parser).
- The web backend must not import from `web.apps.web/` (the frontend) — that directory is not a Python package.
- Tests for the backend live in `tests/unit/web/` and `tests/integration/web/`, mirroring the existing test layout.

## 4. Routers do not do I/O

Routers (under `web/apps/api/routers/`) are thin glue between the cache and the Pydantic models. They:

- Accept query params and a `CachedIndex` dependency.
- Filter / sort / paginate via shared helpers in `routers/_filters.py`.
- Serialize via `routers/_serialize.py`.
- Raise `HTTPException(404)` when a slug doesn't exist.

Routers must not:

- Open files directly. The `CachedIndex` handles all repo I/O.
- Open database sessions directly. As of 8.2 the cache is DB-backed; the materialised `IndexSnapshot` is still the only shape routers see. If a router thinks it needs a SQLAlchemy session, the right move is to extend `CachedIndex` or add a helper under `web/apps/api/db/query.py`.
- Call out to external services. v1 is offline.
- Mutate request state across requests. Each request is a pure function of the snapshot.

## 5. The API surface is typed end to end

Every response body is a Pydantic model declared in `web/apps/api/models.py`. The frontend mirrors those models in `web/apps/web/lib/api-types.ts`.

When you add a field:

1. Add it to the Pydantic model.
2. Mirror it in the TypeScript type.
3. Render it in the relevant frontend component(s).
4. Add a test that pins the wire shape.

When you remove a field, do it in the same order — the frontend stops reading it before the backend stops emitting it.

## 6. Adding a new surface

A "surface" is a route in the sidebar (catalog, queue, threads, …). To add one:

1. Decide the bucket (existing or new). If new, add it to the `Bucket` literal in `web/apps/api/indexer.py` and `models.py`, and to the classification rules in `classify_bucket()`.
2. Add a router under `web/apps/api/routers/<surface>.py` with `GET /<surface>` and `GET /<surface>/{slug}`.
3. Register the router in `web/apps/api/main.py`.
4. Add a Pydantic-typed page under `web/apps/web/app/<surface>/page.tsx` and a detail page under `app/<surface>/[slug]/page.tsx`.
5. Add the surface to the sidebar in `components/Sidebar.tsx`.
6. Add at least one integration test under `tests/integration/web/test_api_<surface>.py`.
7. Update this convention if the surface introduces a new pattern.

## 7. Frontend conventions

- **Server Components by default.** Client components are opt-in (`"use client"`) and reserved for interactivity (filter inputs, search boxes).
- **No data caching across requests.** All fetches use `cache: "no-store"` because the underlying markdown can change between requests. (We revisit when 8.2 lands a persistent index with proper invalidation.)
- **Tailwind utility classes.** Shared style primitives go into `components/`. No emotion / styled-components.
- **Icons via `lucide-react`.** No additional icon libraries.
- **Markdown rendered with `react-markdown` + `remark-gfm`.** No raw HTML interpolation.

## 8. Environments and configuration

- Configuration is env-driven and read once at startup (`web/apps/api/settings.py`).
- Defaults are safe for local dev — `localhost`, port 8000, CORS for `localhost:3000`.
- Secrets do not live in code. When 8.5 introduces auth, secrets live in `.env.local` (gitignored) on each operator's machine and in the deploy target's secret store in production.

## 9. Process

- **Schema changes are PRs that touch the schema doc.** A frontmatter field added without a schema bump fails review.
- **Every PR that touches `web/apps/api/` ships with a test.** No "tests later" exceptions.
- **The runbook is the operator contract.** When you change the runtime story (port, command, env var), update `/command-center/runbooks/web-app.md` in the same change.
- **Quarterly dep upgrade cadence.** A single commit per quarter bumps FastAPI, Next.js, Tailwind, shadcn. Security patches happen immediately.
- **A plan per milestone.** 8.2, 8.3, … each get a plan document in `/docs/plans/` that either updates Phase 8 inline or `supersedes` it.

## 10. What does not belong in /web/

- **Generic Python tools.** Those live in `/tools/` (manifest scanner, etc.).
- **CLI commands.** Those go in `scout/agent/cli.py` (or a new top-level CLI module).
- **Static documentation.** Conventions, plans, and runbooks stay in their existing homes; the web app links to them, not duplicates them.
- **Build artifacts** (`node_modules/`, `.next/`, `__pycache__/`). The `.gitignore` enforces this.
