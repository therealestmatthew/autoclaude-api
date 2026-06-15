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

- **No build / test / lint commands yet.** Phase 0 is markdown only. When Python agents land, commands go in this section.
- **Prefer editing existing assets over creating new ones.** If a new entry would substantially overlap an existing one, propose a merge instead.
- **Don't create README.md or doc files outside the conventions.** Every directory already has a README that defines what belongs in it. Update that README rather than adding sibling docs.
- **Keep the catalog clean.** Drafts and raw finds live in `/scout/queue/`. Only reviewed assets land in `/catalog/`.
- **When in doubt about a convention**, read `/conventions/` first. If the answer isn't there, ask before inventing.

## Phase plan

- **Phase 0 (now):** scaffold, conventions, schema, seed examples.
- **Phase 1:** hand-curate the catalog with assets we already use.
- **Phase 2:** scout v1 — awesome-list parser.
- **Phase 3:** scout v2 — HN / Reddit / Lobsters.
- **Phase 4:** repo extractor (GitHub URL → child assets).
- **Phase 5:** X / Twitter ingestion.
- **Phase 6:** automated merge/dedup decisioning.
- **Phase 7:** command-center observability (token burn, threads).
- **Phase 8+:** consulting buildout.
