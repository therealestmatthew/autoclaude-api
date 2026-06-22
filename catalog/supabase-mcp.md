---
name: supabase-mcp
kind: mcp
title: "Supabase MCP server (hosted)"
status: adopted
quality: 5
tags: [supabase, mcp, hosted, http]
delivery_function: [build, integration]
source:
  type: manual
  url: https://mcp.supabase.com/mcp
  authors: [supabase]
  license: ""
  alternates:
    - type: article
      url: https://supabase.com/docs/guides/getting-started/mcp
discovered:
  via: manual
  on: 2026-06-14
relations:
  parent: supabase
  related: [claude-plugin-supabase, supabase-skill]
fingerprint: ""
created_at: 2026-06-14
updated_at: 2026-06-14

# MCP-specific
mcp:
  transport: http
  endpoint: https://mcp.supabase.com/mcp
  auth_required: true
  configured_via: claude-plugin-supabase
---

# Supabase MCP server

Hosted MCP server operated by Supabase. Configured automatically when the Supabase Claude Code plugin is installed (the plugin's `.mcp.json` points at this endpoint).

## Why parent is `supabase` (org), not `claude-plugin-supabase`

The MCP server is **hosted infrastructure**, not bundled code. The plugin merely *configures Claude Code to talk to it*. The server's lifecycle, code, and operation are Supabase's responsibility, independent of plugin releases. Cataloguing it under the org reflects ownership; the plugin is recorded as a `related:` link.

## What it exposes

Per the plugin description: project management, database work, auth, storage, edge functions, realtime, queues, vectors, cron, migrations, RLS.

## Watch for

- Endpoint changes (we'd notice via a plugin version bump that updates `.mcp.json`).
- Auth model changes (currently requires authentication — see `mcp-needs-auth-cache.json` in `~/.claude/`).
- Schema / capability changes — would affect what the `supabase` skill knows it can call.

## Schema note

This entry uses an `mcp:` extension block (transport, endpoint, auth_required, configured_via) that's not in the canonical schema. See `_schema/notes-from-phase-1.md` for the proposal to formalize per-kind extension blocks.
