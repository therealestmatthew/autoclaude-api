# /catalog/

The master database. A flat collection of `<slug>.md` files, each a polymorphic asset distinguished by `kind:` in frontmatter.

## What belongs here

Anything *collected* — discovered externally and judged worth remembering. Agents, skills, plugins, MCP servers, prompts, repos, articles, people, orgs (see `/conventions/kinds.md`).

## What does NOT belong here

- **Raw, un-reviewed signals.** Those live in `/scout/queue/` until a human reviews them.
- **Our own original IP.** That lives in `/claude/` or `/consulting/`. The catalog is for *collected* things, not invented ones.
- **Notes, todos, scratch.** Not assets. Use the relevant subsystem's own scratch space.

A given thing can be *both* in `/catalog/` and `/claude/`. The catalog entry records origin and our judgment; the `/claude/` copy is the working artifact. When this happens, set the catalog asset's `status: adopted`.

## Structure

```
/catalog/
  _schema/      canonical asset schema + reference
  _examples/    worked examples (don't ship as real catalog entries; they're docs)
  <slug>.md     every other file is a real catalog asset
```

Filenames are slug-only — `kind:` lives in frontmatter. See `/conventions/naming.md`.

## Index

There is intentionally no hand-maintained INDEX.md. Discovery happens via grep:

```sh
# List all assets of a given kind
grep -l '^kind: agent$' *.md

# Find everything tagged code-review
grep -l 'code-review' *.md

# Find what came from a specific source
grep -l 'awesome-claude-code' *.md
```

When we outgrow grep, a generated index gets added in a later phase.

## Adding an asset

1. Read `/conventions/frontmatter.md` and `/catalog/_schema/asset.schema.md`.
2. Pick a slug (`/conventions/naming.md`).
3. Copy the relevant `/catalog/_examples/` file as a starting point.
4. Fill in frontmatter; write the body explaining *why we kept this and how we'd use it*.
5. Set `status: reviewed` (not `draft` — drafts belong in `/scout/queue/`).
