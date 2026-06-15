---
name: claude-md
title: "CLAUDE.md — operating brief for Claude Code in this repo"
kind: convention
status: active
updated_at: 2026-06-15
---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A command-and-control center for an agentic consulting & software-delivery practice. Two business halves (`/consulting/`, `/claude/`) sit on top of three cross-cutting subsystems (`/catalog/`, `/scout/`, `/command-center/`). The repo is markdown-first — git *is* the database. Python tooling will be added as specific agents are built; **no application code exists yet** as of Phase 0.

## Repo layout (and what each dir is for)

```
/conventions/        rules: naming, frontmatter, kinds enum, merge rules, contribution flow
/catalog/            the master DB — flat collection of <slug>.md polymorphic asset files
  /_schema/          canonical schema + spec for an asset
  /_examples/        worked examples (agent, skill, repo + extracted child)
/scout/              discovery pipeline
  /sources/          one YAML per source (HN, Lobsters, Reddit, awesome-lists, X handles)
  /queue/            candidates pending human review
  /state/            per-source cursors (last-seen markers)
  /agent/            Python agent code (empty in Phase 0)
  /extractors/       per-source extractors (empty in Phase 0)
/claude/             agentic-delivery IP we own and use
  /agents/ /skills/ /plugins/ /mcp/ /prompts/ /playbooks/
/consulting/         the consulting business
  /methodologies/    delivery / discovery / estimation playbooks
  /templates/        proposals, SOWs, status reports, retros
  /positioning/ /offers/ /pricing/ /case-studies/   (stubs)
  /engagements/      one folder per client engagement; _template/ is the skeleton
/command-center/     orchestration & observability
  /threads/          log of agentic threads
  /token-burn/       logs + reports
  /runbooks/         how to operate the system
```

## Core conventions (read `/conventions/` for full detail)

- **Markdown + YAML frontmatter everywhere.** No DB, no JSON sidecars. If something isn't expressible in a markdown file, push back before adding infra.
- **Catalog assets are polymorphic.** One file shape, distinguished by `kind:` (agent | skill | plugin | mcp | prompt | repo | article | person | org). Filenames are `<slug>.md` — no kind prefix, no subfolders by kind.
- **The graph lives in `relations:`.** A `repo` asset can have many `agent`/`skill` children via `parent: <repo-slug>`. Use `related:` for peers, `supersedes:` for replacements.
- **Provenance is required.** Every catalog asset carries `source.*` and `discovered.*` blocks so we can trace where it came from and when.
- **Slugs are kebab-case and globally unique** across all kinds. The slug is the asset's identity; renaming it breaks links.

## Where new content goes

| If you have…                                            | Put it in…                       |
| ------------------------------------------------------- | -------------------------------- |
| A raw signal from a discovery source (not yet reviewed) | `/scout/queue/`                  |
| A reviewed, kept asset (anything we want to remember)   | `/catalog/<slug>.md`             |
| An asset we've adopted into our working toolkit         | `/claude/<area>/` **and** keep the catalog entry with `status: adopted` |
| A consulting methodology / template / engagement        | `/consulting/<area>/`            |
| An operator runbook for the system itself               | `/command-center/runbooks/`      |

The catalog is the long-term memory. `/claude/` is what we actively use. An asset can live in both — catalog tracks origin and judgment, `/claude/` is the working copy.

## Scout pipeline (mental model)

```
discovery sources  →  raw signals  →  /scout/queue/  →  human review  →  /catalog/
(socials, awesome-                    (one candidate    (merge into
 lists; GitHub is                      file per find)    existing /
 extraction target,                                      create new /
 NOT a discovery                                         discard)
 surface)
```

GitHub is the *target* of extraction — once we have a repo URL, an extractor (future) clones it and proposes child assets. GitHub is **not** crawled directly for discovery; signals come from socials and curated lists.

## Merge / dedup rules (short version, full in `/conventions/merge-rules.md`)

When reviewing a queue candidate against the catalog:

1. **Fingerprint match** (same `source.url` or `fingerprint:` hash) → update existing, don't create new.
2. **High title/tag overlap** → propose merge; ask before writing.
3. **Same artifact, different source** → keep one canonical asset, add the alternate URL to `source.alternates`.
4. **Genuinely new** → create new asset; if it relates to existing ones, fill `relations.related`.

Phase 0 is human-in-the-loop. Don't auto-merge.

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

uv run ruff check scout/ tests/           # lint
uv run ruff check scout/ tests/ --fix     # autofix safe issues
```

`scout` is exposed as a console script via `pyproject.toml`. The full testing
protocol lives in `/conventions/testing.md`.

### Conventions

- **Prefer editing existing assets over creating new ones.** If a new entry would substantially overlap an existing one, propose a merge instead.
- **Don't create README.md or doc files outside the conventions.** Every directory already has a README that defines what belongs in it. Update that README rather than adding sibling docs.
- **Keep the catalog clean.** Drafts and raw finds live in `/scout/queue/`. Only reviewed assets land in `/catalog/`.
- **When in doubt about a convention**, read `/conventions/` first. If the answer isn't there, ask before inventing.

### Python package layout

```
scout/                    Python package
  _util.py                slugify, canonical_github_url, parse_frontmatter
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
  sources/                YAML configs (data, not Python)
  state/                  per-source persisted state (gitignored at runtime)
  queue/                  candidate markdown files (gitignored at runtime)
tests/
  conftest.py             shared fixtures (sample_candidate, mock httpx factory)
  unit/                   fast, isolated, contract-level tests
  integration/            multi-module flows with isolated filesystem (no network)
    conftest.py           scout_world fixture + auto-applies `integration` marker
  fixtures/               static sample inputs reused across tests
```

The `scout/` directory mixes Python code and data dirs by design — the per-source YAML configs and the queue/state runtime data live next to the code that produces and consumes them. Don't move to a `src/` layout without a strong reason.

When adding a new test, follow `/conventions/testing.md` for which directory it belongs in and what fixtures to reuse.

## Phase plan

- **Phase 0 (done):** scaffold, conventions, schema, seed examples.
- **Phase 1 (done):** hand-curate the catalog with assets we already use.
- **Phase 2 (done):** scout v1 — awesome-list extractor + runner + queue + thread log.
- **Phase 3 (done):** scout v2 — HN / Reddit / Lobsters extractors on the Phase 3.0 security baseline (`scout/_security.py`, `conventions/security.md`).
- **Phase 4 (done):** repo extractor (GitHub URL → child assets), running each clone in a per-clone Docker container per `/conventions/security.md`. Podman runtime is reserved (stub raises `NotImplementedError`).
- **Phase 5:** X / Twitter ingestion.
- **Phase 6:** automated merge/dedup decisioning.
- **Phase 7:** command-center observability (token burn, threads).
- **Phase 8+:** consulting buildout.

## Planning lineage

The phase plan above is a high-level roadmap. The substantive design for each phase — requirements, locked decisions, task breakdown, open questions — lives in this repo under `/docs/plans/`. The lightweight priming prompt that a fresh Claude Code session reads at the start of a phase lives in `/docs/plans/session_prompts/` and points at its sibling plan document.

**Rules:**

- **Plans live in the repo, not on a local machine.** A plan at `~/.claude/plans/<name>.md` (or any other local-only path) is invisible to future sessions, to collaborators, and to the design history. Put the canonical plan at `/docs/plans/<phase-or-feature>.md`. If a planning tool produced a local artifact, copy it into the repo and reference *the in-repo path* from then on.
- **Plans are kept forever.** When a phase is done, the plan is not deleted — it is marked complete (frontmatter `status: done`, `completed_at: <date>`) and stays in place. The design lineage is the audit trail for *why* we built things the way we built them; later phases routinely need to read prior plans to understand non-obvious decisions.
- **Session prompts are short-lived.** They prime a fresh session, are valid only while a phase is in progress, and get renamed `<name>.done.md` (or moved to an archived state) once the phase commits. Plans persist; prompts do not.
- **One plan per phase, named by phase.** `/docs/plans/phase-4-repo-extractor.md`. Mid-phase plans (a meaningful chunk that needs its own plan, e.g., a security baseline landing inside a phase) get their own file rather than mutating the phase plan in-place.

See `/docs/plans/README.md` for the directory layout and frontmatter convention.
