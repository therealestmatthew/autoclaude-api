---
name: web-readme
title: "/web/ — operator UI for the FT-AutoClaude command center"
kind: readme
status: active
updated_at: 2026-06-16
---

# /web/

The browser-based view over this repo. A read layer (v1) and eventually a write layer over the catalog, scout queue, command-center threads, and consulting engagements.

See `/docs/plans/phase-8-web-command-center.md` for the design and the milestone roadmap, and `/conventions/web-app.md` for the rules that govern what lives here.

## Layout

```
/web/
  README.md              this file
  apps/
    api/                 FastAPI backend; part of the ft_autoclaude Python project
    web/                 Next.js 15 frontend; standalone npm project
```

The backend and frontend are intentionally separated so they can deploy independently later (Vercel + Fly.io is the obvious target). The backend has no opinion about which frontend talks to it — `curl` works fine.

## How to run (local dev)

```sh
# Backend (one terminal)
uv sync --group web
uv run ft-autoclaude-api               # FastAPI on http://localhost:8000

# Frontend (another terminal)
cd web/apps/web
npm install
npm run dev                          # Next.js on http://localhost:3000
```

Open `http://localhost:3000` — the sidebar nav gives access to the catalog browser, scout queue review, command-center dashboard, and engagement tracker.

## How it relates to the rest of the repo

- **Reads from**: `/catalog/`, `/scout/queue/`, `/consulting/engagements/`, `/conventions/`, `/docs/plans/`, `/command-center/threads/`. The web app is a *view* — it does not modify any of these in v1.
- **Writes to**: nothing on disk. The in-memory index is rebuilt from `git ls-files` on demand.
- **Replaces**: nothing. CLI commands (`uv run scout *`, `uv run manifest`) remain the primary operator surface; the web app supplements them.

## Maintenance

See `/command-center/runbooks/web-app.md` for operational tasks (start, stop, debug, refresh the index). See `/conventions/web-app.md` for the rules that any new surface or contributor must follow.
