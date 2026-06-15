---
name: supabase-community-claude-plugin
kind: repo
title: "supabase-community/supabase-plugin"
status: adopted
quality: 5
tags: [supabase, claude-code, plugin, mcp]
source:
  type: github
  url: https://github.com/supabase-community/supabase-plugin
  authors: [supabase]
  license: MIT
discovered:
  via: manual
  on: 2026-06-14
relations:
  related: [anthropics-claude-plugins-official]
fingerprint: ""
created_at: 2026-06-14
updated_at: 2026-06-14
---

# supabase-community/supabase-plugin

Upstream repository for the official Supabase plugin for Claude Code. The plugin is *distributed* through `anthropics/claude-plugins-official` (the marketplace) but *developed* here. Catalog both so we can attribute correctly: the marketplace is the distribution channel, the upstream repo is the source of truth for the code and release cadence.

## Children we catalog

- [claude-plugin-supabase](claude-plugin-supabase.md) — the plugin itself.
- [supabase-skill](supabase-skill.md) — the `supabase` skill bundled in the plugin.
- [supabase-postgres-best-practices-skill](supabase-postgres-best-practices-skill.md) — the `supabase-postgres-best-practices` skill bundled in the plugin.

(The MCP server `supabase-mcp` is *referenced* by the plugin but is hosted by Supabase directly, not bundled — see [supabase-mcp](supabase-mcp.md). It's parented to the `supabase` org, not this repo.)

## Watch for

- Plugin version bumps (currently at 0.1.11).
- Skill version bumps inside the plugin (independent — `supabase` v0.1.2, `supabase-postgres-best-practices` v1.1.1 as of this catalog entry).
- Any added skills or agents in the plugin's `skills/` and `agents/` trees.
