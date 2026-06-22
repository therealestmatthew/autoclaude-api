---
name: claude-plugin-supabase
kind: plugin
title: "Supabase plugin for Claude Code"
status: adopted
quality: 5
tags: [supabase, claude-code, plugin, postgres, mcp]
delivery_function: [build, integration]
source:
  type: github
  url: https://github.com/supabase-community/supabase-plugin
  authors: [supabase]
  license: MIT
  alternates:
    - type: github
      url: https://github.com/anthropics/claude-plugins-official
discovered:
  via: manual
  on: 2026-06-14
relations:
  parent: supabase-community-claude-plugin
  related: [anthropics-claude-plugins-official, supabase-mcp]
fingerprint: ""
created_at: 2026-06-14
updated_at: 2026-06-14

# Plugin-specific fields (not yet in the canonical schema — see _schema/notes-from-phase-1.md)
plugin:
  installed_id: supabase@claude-plugins-official
  version_installed: "0.1.11"
  marketplace: anthropics-claude-plugins-official
  install_scope: user
---

# Supabase plugin for Claude Code

Official Supabase plugin installed via `anthropics/claude-plugins-official`. Bundles two skills (`supabase`, `supabase-postgres-best-practices`) and references the hosted Supabase MCP server.

## What ships in the plugin

- **Skills:** [supabase-skill](supabase-skill.md), [supabase-postgres-best-practices-skill](supabase-postgres-best-practices-skill.md).
- **MCP:** the plugin's `.mcp.json` points at the hosted MCP at `https://mcp.supabase.com/mcp`. The MCP itself is catalogued as [supabase-mcp](supabase-mcp.md) and is parented to the `supabase` org (not this plugin), because the server is Supabase-hosted infrastructure, not bundled code.

## How we use it

- The `supabase` skill triggers on anything Supabase-related and enforces the "verify against changelog first" rule that prevents stale-API hallucinations.
- The `supabase-postgres-best-practices` skill is the reference doc when we're writing or reviewing Postgres queries / schemas.
- The MCP gives us project management, database, auth, storage operations from within Claude Code.

## Install metadata

- ID: `supabase@claude-plugins-official`
- Installed version: 0.1.11
- Marketplace repo: `anthropics/claude-plugins-official`
- Install scope: user
- Install path: `~/.claude/plugins/cache/claude-plugins-official/supabase/<version>/`

## Watch for

- Plugin version bumps from upstream.
- Skill version drift inside the plugin — each skill has its own `metadata.version` in its `SKILL.md`. Bumping the plugin doesn't necessarily bump both skills together.
