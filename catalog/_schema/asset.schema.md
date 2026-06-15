# Asset schema

The authoritative spec for a `/catalog/` asset. Every asset is a markdown file with YAML frontmatter, named `<slug>.md`.

## Full example

```yaml
---
name: claude-code-best-practices             # REQUIRED. The slug. Identity.
kind: article                                 # REQUIRED. See kinds.md.
title: "Claude Code Best Practices"           # REQUIRED. Human-readable.
status: reviewed                              # REQUIRED. draft|reviewed|adopted|archived.

quality: 4                                    # Optional. 1–5, our judgment.
tags: [claude-code, agents, workflow]         # Optional. Free-form kebab-case.

source:                                       # REQUIRED.
  type: article                               #   github|x|hn|reddit|awesome-list|article|manual
  url: https://www.anthropic.com/...          #   Canonical URL.
  authors: [anthropic]                        #   Person/org slugs if catalogued.
  license: ""                                 #   Empty for articles; SPDX for code.
  alternates:                                 #   Optional. Other URLs that resolve to same thing.
    - type: hn
      url: https://news.ycombinator.com/item?id=...

discovered:                                   # REQUIRED.
  via: awesome-claude-code                    #   Source slug or 'manual'.
  on: 2026-06-14                              #   ISO date.
  run_id: scout-2026-06-14-001                #   Optional. Set by scout runs.

relations:                                    # Optional.
  parent:                                     #   Slug of the asset this is extracted from.
  related: []                                 #   Peer slugs.
  supersedes: []                              #   Slugs this asset replaces (mark those archived).

fingerprint: ""                               # Optional. Hash of source content. Used by scout to
                                              #   detect changes and avoid re-creating duplicates.

created_at: 2026-06-14                        # REQUIRED. ISO date first added.
updated_at: 2026-06-14                        # REQUIRED. ISO date last meaningful edit.
---

# Body

Free-form markdown: why we kept this, how we use it, what's good about it, what to watch out for.
The frontmatter is for facts and provenance; the body is for our judgment.
```

## Field reference

### `name` (required, string)

The slug. Must equal the filename without `.md`. Kebab-case, globally unique across all kinds. Never change after creation. See `/conventions/naming.md`.

### `kind` (required, enum)

One of: `agent`, `skill`, `plugin`, `mcp`, `prompt`, `repo`, `article`, `person`, `org`. See `/conventions/kinds.md`. Closed enum — adding a value requires a schema change.

### `title` (required, string)

The human-readable name. Can change freely; the slug is the stable identity.

### `status` (required, enum)

- `draft` — not used in `/catalog/`; drafts live in `/scout/queue/`.
- `reviewed` — we've looked at it and decided to keep it. Default state in `/catalog/`.
- `adopted` — we actively use it; a working copy exists in `/claude/` or `/consulting/`.
- `archived` — superseded, removed upstream, or no longer relevant. Keep the file for history.

### `quality` (optional, 1–5)

Our subjective rating after review. Omit until reviewed. 5 = we'd recommend it unprompted; 1 = kept for completeness only.

### `tags` (optional, list of strings)

Free-form kebab-case. Used for grep/filter and merge hints. Prefer reusing existing tags over inventing new ones — grep before adding.

### `source` (required, object)

Where the asset originally lives in the world.

- `source.type` — `github` | `x` | `hn` | `reddit` | `awesome-list` | `article` | `manual`.
- `source.url` — canonical URL of the artifact itself.
- `source.authors` — list of `person`/`org` slugs from our catalog (or string names if not yet catalogued).
- `source.license` — SPDX identifier for code; empty for articles.
- `source.alternates` — optional list of other URLs that resolve to the same asset.

### `discovered` (required, object)

How *we* found it. Distinct from `source` — `source` is where it lives, `discovered` is the trail that led us to it.

- `discovered.via` — slug of the discovery source (`hackernews`, `awesome-claude-code`, etc.) or `manual`.
- `discovered.on` — ISO date.
- `discovered.run_id` — set by scout runs; manual additions omit.

### `relations` (optional, object)

The graph layer over the flat collection.

- `relations.parent` — slug of the asset this is extracted from. E.g., an `agent` extracted from a scouted `repo` sets `parent: <repo-slug>`.
- `relations.related` — list of peer slugs. Symmetric in intent; we don't enforce mirror updates.
- `relations.supersedes` — list of slugs this asset replaces. Mark those `status: archived` in the same change.

### `fingerprint` (optional, string)

Hash of source content (algorithm TBD when extractor lands — likely `sha256:<hex>`). Used by scout to detect when an upstream change warrants an update vs a new asset.

### `created_at`, `updated_at` (required, ISO date)

`created_at` never changes. `updated_at` bumps on every meaningful edit.

## Validation (future)

A linter will be added in a later phase to enforce required fields, slug ↔ filename match, and `kind` enum membership. For now, this spec is the source of truth; review enforces it.
