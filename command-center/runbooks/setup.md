# Setup — running FT-AutoClaude on a new machine

End-to-end guide for porting FT-AutoClaude to a fresh environment (typically your work laptop). Tested order. Each step's success criterion is on the line below the command.

---

## Prerequisites

Install these first. Versions are minimums.

| Tool | Version | Why | How |
|------|---------|-----|-----|
| **Python** | 3.11+ | Backend + CLI tools | Easiest: `uv python install 3.13` |
| **uv** | latest | Python package management | https://docs.astral.sh/uv/getting-started/installation/ |
| **Node.js** | 20+ | Next.js 15 frontend | https://nodejs.org/ (or nvm / fnm) |
| **git** | any recent | Repo clone | OS package manager |

You do **not** need to install Anthropic CLIs, Postgres, or anything else — the API uses SQLite by default and the catalog has no external runtime dependencies.

---

## Steps

### 1. Clone the repo

```sh
git clone <your-repo-url> ft-autoclaude
cd ft-autoclaude
```

### 2. Install Python dependencies

```sh
uv sync
```
This creates `.venv/` and installs the runtime + dev groups (~30 seconds first time).

### 3. Install web app dependencies

```sh
cd web/apps/web && npm install && cd -
```
~1 minute first time.

### 4. Verify the environment

```sh
uv run ft-autoclaude-doctor
```

Expected output: a checklist with all green checks (or one `info` line about `.env.local`). If anything is red, the doctor prints a fix hint for it.

To also confirm the API server can boot, run the doctor with `--api` *after* you've started the API (step 6 below).

### 5. Run the test suite (optional but recommended)

```sh
uv run pytest tests/unit -q
```
Should report `342 passed` (or similar). A failure here means an environment issue, not a config issue.

### 6. Start the dev servers

Two processes, two terminals.

**Terminal A — API backend (port 8000):**
```sh
uv run ft-autoclaude-api
```
First boot creates `web/.data/index.sqlite` and runs migrations. Subsequent boots are instant.

**Terminal B — web frontend (port 3001):**
```sh
cd web/apps/web && npm run dev
```

Open http://localhost:3001 in a browser.

### 7. First commands to try

- **Browse the catalog** — http://localhost:3001/catalog (~14 Anaplan-flavored seed entries pre-loaded)
- **By Function view** — http://localhost:3001/skills?view=function (organized by Anaplan delivery phase)
- **Run scout** (pulls candidate items from sources):
  ```sh
  uv run scout run -v
  ```
- **Build a static share bundle**:
  ```sh
  uv run ft-autoclaude-export-static
  ```
  Output: `dist/catalog-static/` — see [static-export.md](static-export.md).

---

## Updating later

When you pull new changes from the repo:

```sh
git pull
uv sync                                    # picks up new Python deps
cd web/apps/web && npm install && cd -     # picks up new JS deps
uv run ft-autoclaude-doctor                # confirms nothing broke
```

The API auto-runs new DB migrations on boot. You should not need to run `uv run ft-autoclaude-index upgrade` manually except in unusual cases.

---

## Troubleshooting

**`uv: command not found`** — uv isn't on your PATH. Either reinstall it from the link above, or use `~/.local/bin/uv` explicitly.

**`Python interpreter not found`** — Run `uv python install 3.13` and retry. `uv sync` will then provision the interpreter.

**`npm install` hangs or errors** — Delete `web/apps/web/node_modules` and `package-lock.json`, then retry. If on a corporate network, you may need to set `npm config set registry https://<your-internal-mirror>`.

**API boots but the web UI shows "API offline"** — Check `NEXT_PUBLIC_API_URL` in `web/apps/web/.env.local` (or create one based on `.env.example`). Default is `http://localhost:8000`.

**Port already in use** — Both 8000 (API) and 3001 (web) can be remapped via `FT_AUTOCLAUDE_PORT` (API) and `next dev --port <n>` (web).

**Tests fail with permission errors** — Usually a stale `.pytest_cache/` or `web/.data/`. Delete and rerun.
