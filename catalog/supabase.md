---
name: supabase
kind: org
title: "Supabase"
status: adopted
quality: 5
tags: [supabase, postgres, backend-as-a-service, mcp]
source:
  type: manual
  url: https://supabase.com
  authors: []
  license: ""
  alternates:
    - type: github
      url: https://github.com/supabase
    - type: github
      url: https://github.com/supabase-community
discovered:
  via: manual
  on: 2026-06-14
relations:
  related: []
created_at: 2026-06-14
updated_at: 2026-06-14
---

# Supabase

Postgres-based backend-as-a-service. Author of the official Supabase plugin for Claude Code (`claude-plugin-supabase`) and the hosted Supabase MCP server (`supabase-mcp`).

## Why this is in the catalog

Reference target for `source.authors` on Supabase-published assets — the plugin, both bundled skills, the MCP server, and any Supabase blog posts / docs we catalog later.

## Things to watch

- The `supabase-community/supabase-plugin` repo (plugin releases).
- The `supabase/supabase` repo (product changes that affect what the skill knows).
- Supabase changelog (`supabase.com/changelog.md`) — the `supabase` skill itself flags this as the canonical place to check before implementing anything.
- MCP server changes at `mcp.supabase.com`.
