---
name: claude-md
title: "CLAUDE.md — operating brief for Claude Code in this repo"
kind: convention
status: active
updated_at: 2026-06-19
---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

**FT-AutoClaude — an Agentic Solutions Marketplace for Finance Transformation consulting.** A private hard-fork of the open-source `autoclaude` command-and-control center, retargeted for a Finance Transformation consulting practice. Two business halves (`/consulting/`, `/claude/`) sit on top of three cross-cutting subsystems (`/catalog/`, `/scout/`, `/command-center/`). The repo is markdown-first — git *is* the database — with a Python + FastAPI backend and Next.js operator UI on top.

Phase 10 introduces per-client branding, document templates that bundle brand + content for export, asset notes with audit semantics, a business-process taxonomy, and a marketplace-shaped UI on top of the existing catalog. The strategic blueprint and locked decisions live at `/docs/plans/company-edition.md` — read that before proposing architectural changes.

## Repo layout (and what each dir is for)

```
/conventions/        rules: naming, frontmatter, kinds enum, merge rules, contribution flow
/catalog/            the master DB — flat collection of <slug>.md polymorphic asset files
  /_schema/          canonical schema + spec for an asset
  /_examples/        worked examples (agent, skill, repo + extracted child)
  /templates/        (Phase 10.2+) PPTX/DOCX/XLSX deliverable templates with .meta.yaml sidecars
  /bundles/          (Phase 10.2+) bundle compositions (template + generator + brand resolution)
/scout/              discovery pipeline
  /sources/          one YAML per source (HN, Lobsters, Reddit, awesome-lists, X handles)
  /queue/            candidates pending human review
  /state/            per-source cursors (last-seen markers)
  /agent/            Python orchestrator
  /extractors/       per-source extractors
  /reviewer/         (Phase 9.0) LLM-driven triage agent
/claude/             agentic-delivery IP we own and use
  /agents/ /skills/ /plugins/ /mcp/ /prompts/ /playbooks/
/consulting/         the consulting business
  /methodologies/    delivery / discovery / estimation playbooks
    /templates/      proposals, SOWs, status reports, retros (prose templates — Phase 10.0 rename)
  /positioning/ /offers/ /pricing/ /case-studies/   (stubs)
  /engagements/      one folder per client engagement; _template/ is the skeleton
/clients/            (Phase 10.1+) one folder per client; brand reference + context
/brands/             (Phase 10.1+) <client-slug>/brand.md + binary assets (logos, fonts, masters)
/domain/             (Phase 10.4+) finance-transformation ontology (glossary, process map)
/command-center/     orchestration & observability
  /threads/          log of agentic threads
  /token-burn/       logs + reports
  /runbooks/         how to operate the system
/web/                Phase 8+ web command center (operator UI)
  /apps/api/         FastAPI backend; part of the ft_autoclaude Python project
  /apps/web/         Next.js 15 + Tailwind frontend; standalone npm project
/tools/              CLI entry points (web, index, manifest) — thin wrappers around web/apps/api
```

## Core conventions (read `/conventions/` for full detail)

- **Markdown + YAML frontmatter everywhere.** No DB-only state for catalog content. If something isn't expressible in a markdown file, push back before adding infra. (Operational DB entities like `client`, `note`, `export_job` are the documented exceptions — see `/docs/plans/company-edition.md`.)
- **Catalog assets are polymorphic.** One file shape, distinguished by `kind:`. The kind enum is split into `catalog_kind` (closed, governs `/catalog/` + `/brands/`) and `document_kind` (open, governs READMEs, conventions, plans, etc.). See `/conventions/kinds.md`. Filenames are `<slug>.md` — no kind prefix, no subfolders by kind (except the curated `templates/` and `bundles/` subdirs).
- **The graph lives in `relations:`.** A `repo` asset can have many `agent`/`skill` children via `parent: <repo-slug>`. Use `related:` for peers, `supersedes:` for replacements.
- **Provenance is required.** Every catalog asset carries `source.*` and `discovered.*` blocks so we can trace where it came from and when. Operator-authored entities (clients, brands) live in DB tables and skip provenance — that's intentional.
- **Slugs are kebab-case and globally unique** within their bucket. Slug-FKs from DB tables to catalog assets are protected by a rename guardrail: renaming a referenced asset returns `409 referenced-by` unless `?cascade=true` is passed.

## Where new content goes

| If you have…                                            | Put it in…                       |
| ------------------------------------------------------- | -------------------------------- |
| A raw signal from a discovery source (not yet reviewed) | `/scout/queue/`                  |
| A reviewed, kept asset (anything we want to remember)   | `/catalog/<slug>.md`             |
| An asset we've adopted into our working toolkit         | `/claude/<area>/` **and** keep the catalog entry with `status: adopted` |
| A consulting methodology / template (prose)             | `/consulting/methodologies/`     |
| A consulting engagement                                 | `/consulting/engagements/<year>-<client>/` |
| A client identity + brand reference                     | `/clients/<slug>/` + `/brands/<slug>/` (Phase 10.1+) |
| A deliverable template (PPTX/DOCX/XLSX)                 | `/catalog/templates/<slug>.md` + `files/<slug>.<ext>` (Phase 10.2+) |
| A bundle composition (template + generator + brand)     | `/catalog/bundles/<slug>.md` (Phase 10.2+) |
| Finance-transformation domain knowledge                 | `/domain/finance-transformation/` (Phase 10.4+) |
| An operator runbook for the system itself               | `/command-center/runbooks/`      |
| Browser UI changes (catalog browser, dashboard, …)      | `/web/apps/api/` + `/web/apps/web/` — see `/conventions/web-app.md` |

The catalog is the long-term memory. `/claude/` is what we actively use. An asset can live in both — catalog tracks origin and judgment, `/claude/` is the working copy.

## Scout pipeline (mental model)

```
discovery sources  →  raw signals  →  /scout/queue/  →  reviewer agent  →  /catalog/
(socials, awesome-                    (one candidate    (9.0 LLM
 lists; GitHub is                      file per find)    triage with
 extraction target,                                      operator gate)
 NOT a discovery
 surface)
```

GitHub is the *target* of extraction — once we have a repo URL, an extractor clones it (in a per-clone Docker container per `/conventions/security.md`) and proposes child assets. GitHub is **not** crawled directly for discovery; signals come from socials and curated lists.

## Merge / dedup rules (short version, full in `/conventions/merge-rules.md`)

When reviewing a queue candidate against the catalog:

1. **Fingerprint match** (same `source.url` or `fingerprint:` hash) → update existing, don't create new.
2. **High title/tag overlap** → propose merge; ask before writing.
3. **Same artifact, different source** → keep one canonical asset, add the alternate URL to `source.alternates`.
4. **Genuinely new** → create new asset; if it relates to existing ones, fill `relations.related`.

The reviewer agent (Phase 9.0) writes proposals to a DB table; an operator triages via the `/proposals` UI.

## Working in this repo

### Setup (one time)

Install [uv](https://docs.astral.sh/uv/), then:

```sh
uv sync                            # creates .venv, installs runtime + dev group
uv sync --no-dev                   # runtime deps only
```

### Commands (all via `uv run`, no manual venv activation)

```sh
uv run scout run                          # all enabled sources, writes to /scout/queue/
uv run scout run -v                       # verbose
uv run scout run -s awesome-lists         # one source by slug (matches /scout/sources/<slug>.yaml)

uv run pytest                             # full suite (unit + integration)
uv run pytest tests/unit                  # unit only
uv run pytest tests/integration           # integration only
uv run pytest -m "not integration"        # marker-based filter (equivalent to unit-only)
uv run pytest -k slugify                  # filter by name substring

uv run ruff check scout/ web/ tests/      # lint
uv run ruff check scout/ web/ tests/ --fix # autofix safe issues

uv run ft-autoclaude-api                  # FastAPI backend for the web UI on :8000
( cd web/apps/web && npm run dev )        # Next.js frontend on :3000 (requires `npm install` first)

uv run scout review --dry-run             # reviewer agent: preview decisions (no writes; no API key spend)
uv run scout review --limit 25            # reviewer agent: generate pending proposals (API key + API server required)
uv run scout review --evals               # eval harness: score against golden set (API key required)

uv run ft-autoclaude-index sync           # populate / refresh the persistent index (SQLite default at web/.data/index.sqlite)
uv run ft-autoclaude-index status         # show current sync state
uv run ft-autoclaude-index upgrade        # alembic upgrade head; rarely needed (API auto-migrates on boot)
```

`scout`, `ft-autoclaude-api`, and `ft-autoclaude-index` are exposed as console scripts via `pyproject.toml`. Environment variables for the web stack are prefixed `FT_AUTOCLAUDE_*` (see `/command-center/runbooks/web-app.md`). The full testing protocol lives in `/conventions/testing.md`; web app rules live in `/conventions/web-app.md`; the web runbook lives at `/command-center/runbooks/web-app.md`. The persistent-index design lives at `/docs/plans/phase-8-2-persistent-index.md`.

### Conventions

- **Prefer editing existing assets over creating new ones.** If a new entry would substantially overlap an existing one, propose a merge instead.
- **Don't create README.md or doc files outside the conventions.** Every directory already has a README that defines what belongs in it. Update that README rather than adding sibling docs.
- **Keep the catalog clean.** Drafts and raw finds live in `/scout/queue/`. Only reviewed assets land in `/catalog/`.
- **When in doubt about a convention**, read `/conventions/` first. If the answer isn't there, ask before inventing.

### Python project layout

```
scout/                    discovery subsystem (Python package)
  _util.py                slugify, canonical_github_url, parse_frontmatter
  _security.py            Phase 3.0 security baseline shared by extractors
  agent/
    types.py              Candidate, SourceState, per-source config models
    runner.py             run_once orchestrator
    cli.py                argparse entry point (exposes `scout` script)
  _container.py           Phase 4 — locked-flag docker/podman wrapper
  clone_runner/           Phase 4 — Dockerfile + entrypoint.sh for the
                          per-clone sandbox image (scout-clone-runner)
  extractors/
    base.py               Extractor Protocol
    awesome_list.py       Phase 2 extractor
    repo.py               Phase 4 extractor
    hackernews.py, reddit.py, lobsters.py   Phase 3 extractors
  reviewer/               Phase 9.0 LLM triage agent
  sources/                YAML configs (data, not Python)
  state/                  per-source persisted state (gitignored at runtime)
  queue/                  candidate markdown files (gitignored at runtime)
tools/                    CLI entry-point wrappers
  web.py                  → `ft-autoclaude-api`
  index.py                → `ft-autoclaude-index`
  manifest.py             → `manifest` (frontmatter scanner)
web/apps/api/             FastAPI backend (Phase 8+)
  db/                     SQLAlchemy models, session, sync engine
  routers/                catalog, queue, engagements, conventions, plans, proposals, threads, …
  writes/                 8.3 write-back: fs/git/editor/triage/audit
migrations/               Alembic — schema versioned at 0002 (8.3); 10.x adds 0003+
tests/
  conftest.py             shared fixtures (sample_candidate, mock httpx factory)
  unit/                   fast, isolated, contract-level tests
  integration/            multi-module flows with isolated filesystem (no network)
  evals/                  golden-set harness (Phase 9.0 reviewer)
```

The `scout/` directory is the **discovery subsystem** (Python package + its YAML data + runtime queue/state). It mixes Python code and data dirs by design — the per-source configs and runtime data live next to the code that produces and consumes them. The directory name predates the FT-AutoClaude rebrand and is preserved as a meaningful subsystem name; do not rename it.

When adding a new test, follow `/conventions/testing.md` for which directory it belongs in and what fixtures to reuse.

## Phase plan

- **Phase 0 (done):** scaffold, conventions, schema, seed examples.
- **Phase 1 (done):** hand-curate the catalog with assets we already use.
- **Phase 2 (done):** scout v1 — awesome-list extractor + runner + queue + thread log.
- **Phase 3 (done):** scout v2 — HN / Reddit / Lobsters extractors on the Phase 3.0 security baseline.
- **Phase 4 (done):** repo extractor running each clone in a per-clone Docker container.
- **Phase 5:** X / Twitter ingestion (deferred).
- **Phase 6:** automated merge/dedup decisioning (designed in 9.0 plan, not yet shipped).
- **Phase 7 (done):** command-center observability (token burn, threads).
- **Phase 8 (done):** web command center — operator UI over catalog/queue/threads/engagements.
- **Phase 9.0 (done):** reviewer agent — LLM-driven keep/merge/discard proposals.
- **Phase 10 (active — FT-AutoClaude pivot):** company edition. Clients, brands, templates, bundles, export pipeline, business-process taxonomy, marketplace UX, configurable sidebar, drag/drop ingestion, cloud-readiness seams. See `/docs/plans/company-edition.md`.
  - **10.0 (done):** fork, project rename (`autoclaude` → `ft_autoclaude`; CLI `autoclaude-*` → `ft-autoclaude-*`; env `AUTOCLAUDE_*` → `FT_AUTOCLAUDE_*`), schema hygiene (kind enum split into `catalog_kind` + `document_kind`; `/consulting/templates/` moved under `/consulting/methodologies/`; brand `.meta.yaml` exception documented).
  - **10.1 → 10.8:** client/brand entity, templates+bundles+export pipeline, notes+sensitivity, taxonomy+ontology+voice, marketplace UX+approval workflow, sidebar, ingestion (markdown + tabular), cloud-readiness pass.
- **Phase 11+:** AWS deploy (Cognito, RDS, S3, ECS, CloudFront, Secrets Manager). Workflow builder. Granular RBAC.

## Planning lineage

The phase plan above is a high-level roadmap. The substantive design for each phase — requirements, locked decisions, task breakdown, open questions — lives in this repo under `/docs/plans/`. The lightweight priming prompt that a fresh Claude Code session reads at the start of a phase lives in `/docs/plans/session_prompts/` and points at its sibling plan document.

**Rules:**

- **Plans live in the repo, not on a local machine.** A plan at `~/.claude/plans/<name>.md` (or any other local-only path) is invisible to future sessions, to collaborators, and to the design history. Put the canonical plan at `/docs/plans/<phase-or-feature>.md`. If a planning tool produced a local artifact, copy it into the repo and reference *the in-repo path* from then on.
- **Plans are kept forever.** When a phase is done, the plan is not deleted — it is marked complete (frontmatter `status: done`, `completed_at: <date>`) and stays in place. The design lineage is the audit trail for *why* we built things the way we built them; later phases routinely need to read prior plans to understand non-obvious decisions.
- **Session prompts are short-lived.** They prime a fresh session, are valid only while a phase is in progress, and get renamed `<name>.done.md` (or moved to an archived state) once the phase commits. Plans persist; prompts do not.
- **One plan per phase, named by phase.** `/docs/plans/phase-4-repo-extractor.md`. Mid-phase plans (a meaningful chunk that needs its own plan, e.g., a security baseline landing inside a phase) get their own file rather than mutating the phase plan in-place.

See `/docs/plans/README.md` for the directory layout and frontmatter convention.
