---
name: runbook-web-app
title: "Runbook — start, stop, debug the web command center"
kind: runbook
status: active
when_to_run: "Any time you need to run, debug, or refresh the /web/ surface."
last_used:
last_verified: 2026-06-17
updated_at: 2026-06-17
# 2026-06-17: 8.3 backend (write-back + proposals) is now wired; the
# frontend pages described below are 8.3b follow-up.
---

# Runbook — Web command center

Operational tasks for the Phase 8 web app at `/web/`. Keep this file accurate; an operator should be able to act on it without reading the source.

## Pre-flight

```sh
# Install web deps if you haven't (re-running this is idempotent).
uv sync --group web
# Node is required for the frontend.
node --version    # expect >= 20
```

## Start (local)

Two terminals.

```sh
# Terminal A — backend
uv run ft-autoclaude-api
# → INFO: Uvicorn running on http://127.0.0.1:8000
```

```sh
# Terminal B — frontend
cd web/apps/web
npm install      # first time only
npm run dev
# → ready - started server on 0.0.0.0:3000
```

Open `http://localhost:3000`. The sidebar shows Dashboard, Catalog, Queue, Threads, Engagements, Conventions, Plans.

## Smoke checks

```sh
curl -s http://localhost:8000/health | jq
# expect: {"ok": true, "records": <n>, ...}

curl -s http://localhost:8000/stats | jq '.stats.by_bucket'
# expect: catalog/queue counts > 0
```

## Refresh the index

The persistent index lives at `web/.data/index.sqlite` and is rebuildable from the repo at any time. The API drives an initial sync on startup and runs a background reconciler every 60 seconds, so most edits surface within a minute. Force a sync explicitly when you need it immediately:

```sh
curl -s -X POST http://localhost:8000/sync | jq
# or, without the API running:
uv run ft-autoclaude-index sync
```

If the schema is wrong (or doesn't exist yet), upgrade it:

```sh
uv run ft-autoclaude-index upgrade        # alembic upgrade head
uv run ft-autoclaude-index status         # show meta + record count
uv run ft-autoclaude-index reset --yes    # drop + re-migrate + re-sync from scratch
```

By default the API runs `alembic upgrade head` automatically on boot, so the only time you'd run `upgrade` by hand is in a deploy script that prefers explicit migrations. Set `FT_AUTOCLAUDE_INDEX_AUTO_MIGRATE=0` to disable the on-boot upgrade.

## Stop

`Ctrl+C` in each terminal. No persistent state to clean up.

## Configuration

Backend env vars (read once at startup):

| Var                          | Default                                              | What it controls                          |
| ---------------------------- | ---------------------------------------------------- | ----------------------------------------- |
| `FT_AUTOCLAUDE_REPO_ROOT`       | the repo containing `web/apps/api/`                  | where the indexer walks                   |
| `FT_AUTOCLAUDE_API_HOST`        | `127.0.0.1`                                          | bind host                                 |
| `FT_AUTOCLAUDE_API_PORT`        | `8000`                                               | bind port                                 |
| `FT_AUTOCLAUDE_API_CORS_ORIGINS`| `http://localhost:3000,http://127.0.0.1:3000`        | comma-separated allowed origins           |
| `FT_AUTOCLAUDE_API_LOG_LEVEL`   | `info`                                               | uvicorn log level                         |
| `FT_AUTOCLAUDE_INDEX_DSN`       | `sqlite:///web/.data/index.sqlite` (resolved against `FT_AUTOCLAUDE_REPO_ROOT`) | SQLAlchemy connection string. Override for Postgres in 8.5. |
| `FT_AUTOCLAUDE_INDEX_RECONCILE_INTERVAL` | `60`                                        | seconds between background syncs; `0` disables the loop (useful in tests). |
| `FT_AUTOCLAUDE_INDEX_AUTO_MIGRATE`| `1`                                                | run `alembic upgrade head` on API boot. Set `0` in production / CI to make migrations an explicit deploy step. |
| `FT_AUTOCLAUDE_GIT_AUTHOR_NAME`   | falls back to `git config user.name`               | author of web-driven commits (8.3 write-back). |
| `FT_AUTOCLAUDE_GIT_AUTHOR_EMAIL`  | falls back to `git config user.email`              | author email of web-driven commits. The backend refuses to write if neither env nor git config provides one. |

Frontend env vars (`web/apps/web/.env.local`):

| Var                  | Default                | What it controls               |
| -------------------- | ---------------------- | ------------------------------ |
| `NEXT_PUBLIC_API_URL`| `http://localhost:8000`| where the frontend hits the API|

## Common failures

### "API unreachable" banner on every page

The frontend can't reach the backend. Check:

1. Is `uv run ft-autoclaude-api` running? `curl http://localhost:8000/health` should respond.
2. Does `NEXT_PUBLIC_API_URL` match the backend bind? Restart `npm run dev` after editing `.env.local`.
3. Is the backend's CORS allow-list permitting the frontend's origin?

### "Address already in use" on `uv run ft-autoclaude-api`

Something else is on :8000. Find it:

```sh
lsof -i :8000
```

Either stop that process or run with a different port:

```sh
FT_AUTOCLAUDE_API_PORT=8001 uv run ft-autoclaude-api
# remember to also bump NEXT_PUBLIC_API_URL on the frontend
```

### `ModuleNotFoundError: fastapi`

The web deps aren't installed. Run `uv sync --group web` (or `uv sync` if `dev` includes them, which it does for the test suite).

### `no such table: asset`

The DB schema isn't initialised. The API auto-migrates on boot by default; this error usually means `FT_AUTOCLAUDE_INDEX_AUTO_MIGRATE=0` is set or the DSN points somewhere the migrations haven't been applied. Fix:

```sh
uv run ft-autoclaude-index upgrade
```

If the DB ended up in an unrecoverable state (e.g. mid-development schema churn), wipe and start fresh:

```sh
uv run ft-autoclaude-index reset --yes
```

### Catalog asset shows up with an "issues" badge

The indexer flagged a parse or required-field problem. The badge text matches one of:

- `missing-frontmatter` — file has no `---` block at all
- `malformed-frontmatter` — YAML couldn't parse
- `missing-name` / `missing-title` — required field absent for the bucket
- `slug-collision:<other-path>` — another file already uses this slug

Fix the file in your editor; the cache auto-rebuilds on the next request.

### Frontend builds but pages 500 with "Cannot read property of undefined"

Likely an API shape mismatch — the backend changed but `lib/api-types.ts` wasn't updated. Sync the types and restart `npm run dev`.

## Tests

```sh
uv run pytest tests/unit/web -q
uv run pytest tests/integration/web -q
```

`/conventions/web-app.md` requires every router PR to ship a test. CI (when added) enforces this.

## What lives where

| Concern                       | Location                                |
| ----------------------------- | --------------------------------------- |
| Architectural rules           | `/conventions/web-app.md`               |
| Phase plan + roadmap          | `/docs/plans/phase-8-web-command-center.md` |
| Persistent-index plan         | `/docs/plans/phase-8-2-persistent-index.md` |
| Backend code                  | `/web/apps/api/`                        |
| Persistent-index code         | `/web/apps/api/db/` + `/web/migrations/` |
| Frontend code                 | `/web/apps/web/`                        |
| Entry-point scripts           | `/tools/web.py` → `uv run ft-autoclaude-api`, `/tools/index.py` → `uv run ft-autoclaude-index` |
| Tests                         | `/tests/unit/web/`, `/tests/integration/web/` |
| Test fixtures                 | `/tests/fixtures/web/sample_repo/`      |
| SQLite (gitignored)           | `/web/.data/index.sqlite`               |
| Write-back service layer      | `/web/apps/api/writes/`                  |
| Write-back endpoints          | `/web/apps/api/routers/writes.py`, `proposals.py` |
| Write-back plan               | `/docs/plans/phase-8-3-write-back.md`   |

## Last-verified policy

This runbook is `status: active` only while `last_verified` is within 90 days of the current date. When you run end-to-end and confirm the surface still works, bump `last_verified` in the frontmatter. If the date drifts past 90 days, the manifest scanner flags it `status: stale` and it needs a re-verification pass before further work.
