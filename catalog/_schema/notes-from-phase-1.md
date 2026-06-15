# Schema friction — notes from Phase 1 seeding

Friction observed while writing the first eight real catalog entries (`anthropic`, `supabase`, two repos, one plugin, two skills, one MCP). Inputs to a future schema iteration; **not yet changes to the canonical schema** in `asset.schema.md`.

## 1. `relations.parent` needs to accept non-repo kinds

**What happened:** the Supabase MCP server (`supabase-mcp`) is hosted infrastructure, not bundled code. Its natural parent isn't a repo — it's the `supabase` org. I parented it to `kind: org` and it read fine.

**Proposed change:** explicitly document that `parent:` accepts any kind. Add examples for `parent: <org>` and `parent: <person>` to `asset.schema.md`. Today the schema implies repo only ("e.g., an `agent` extracted from a scouted `repo`").

**Why this matters:** any first-party Claude Code asset (built-in skills, built-in agents) parents most naturally to `anthropic` (org), because Claude Code itself is a closed product with no clonable repo. Without this, we'd be forced to invent a `claude-code` repo asset with a misleading source URL.

## 2. Versioning isn't expressed in the schema

**What happened:** plugins and skills both ship versions, and they drift independently. The Supabase plugin is at 0.1.11; inside it, the `supabase` skill is at 0.1.2 and `supabase-postgres-best-practices` is at 1.1.1. None of those are first-class fields today.

**I used:** per-kind extension blocks (`plugin: { version_installed: "0.1.11", … }`, `skill: { version_installed: "1.1.1" }`, `mcp: { transport, endpoint, … }`) to capture them inline. Worked, but is undocumented.

**Proposed change:** formalize either
- (a) a top-level optional `version:` string field; **or**
- (b) per-kind extension blocks as a documented pattern (`plugin:`, `skill:`, `mcp:`, `repo:`, …), each with its own optional schema.

I lean (b) because the fields that matter differ per kind (an `mcp` cares about transport/endpoint; a `plugin` cares about install ID and marketplace; a `repo` cares about default branch). One flat `version:` would not be enough.

## 3. "Adopted" status with multiple version snapshots

**What happened:** an adopted asset has a *current installed version*, but upstream keeps releasing. The catalog entry captures the version we adopted, but we also want to know what's current upstream.

**Proposed change:** consider a `version_upstream:` field alongside `version_installed:`, with a clear update procedure (the catalog tracks our state; a future scout extractor or a runbook updates `version_upstream:` periodically). Not blocking now — but worth designing before we have 100 adopted assets and 50 of them are stale.

## 4. Closed-source / hosted products don't fit `kind: repo`

**What happened:** Claude Code itself, and the hosted Supabase MCP, are real assets that don't have a clonable repo. I sidestepped Claude Code by not making it an asset (its "owner" is the `anthropic` org, which is enough), and the hosted MCP fit `kind: mcp` cleanly because that's what it is.

**Decision:** no new kind needed yet. If we end up wanting to catalog closed products as first-class assets (e.g. "Claude Code 4.7" as a thing with a release date and changelog), revisit with a `kind: product` proposal — but resist until a real need shows up.

## 5. Plugin distribution channel vs. upstream source

**What happened:** the Supabase plugin's *upstream* repo is `supabase-community/supabase-plugin`; the *distribution* repo is `anthropics/claude-plugins-official` (the marketplace). I catalogued both as separate `repo` assets with a `relations.related:` link, and the plugin's `source.url` points to upstream with `source.alternates` pointing to the marketplace.

**This worked**, but it's a pattern worth documenting in `/conventions/` so future scouted plugins follow the same convention rather than inventing variations.

## 6. The "installed_at" / "adopted_on" trail isn't captured

**What happened:** the plugin metadata in `installed_plugins.json` has `installedAt` and `lastUpdated`. Useful provenance ("we've used this since X"), but no obvious frontmatter home.

**Proposed change:** optional `adopted_on:` (ISO date) for any asset with `status: adopted`. Distinct from `discovered.on` (when we first found it) and `created_at` (when the catalog entry was written).

---

## What I am NOT proposing

- A linter to enforce all this. Still cheaper to enforce by review.
- A separate file per kind's extension schema. Document inline in `asset.schema.md` when we formalize.
- A migration of the eight Phase 1 entries — they'll be updated *in place* when the schema iterates. That's the cost of moving fast in Phase 1.

## Next step

Roll these into a schema-iteration PR after Phase 2 (awesome-list scout) shakes out a few more friction points. Don't iterate the schema on a sample of one phase's worth of evidence.
