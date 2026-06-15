---
name: supabase-skill
kind: skill
title: "Skill: supabase"
status: adopted
quality: 5
tags: [supabase, skill, postgres, claude-code]
source:
  type: github
  url: https://github.com/supabase-community/supabase-plugin/tree/main/skills/supabase
  authors: [supabase]
  license: MIT
discovered:
  via: manual
  on: 2026-06-14
relations:
  parent: claude-plugin-supabase
  related: [supabase-postgres-best-practices-skill]
fingerprint: ""
created_at: 2026-06-14
updated_at: 2026-06-14

# Skill-specific
skill:
  version_installed: "0.1.2"
---

# Skill: supabase

The Supabase plugin's primary skill. Triggers on anything Supabase-related — products, client libraries, auth, schema/migrations, extensions, MCP usage.

## Core principles it enforces

1. **Don't rely on training data for Supabase features.** Verify against `supabase.com/changelog.md` first, then look up specifics in current docs.
2. **Verify your work.** After implementing, run a test query that confirms the change.

These map directly to the agentic-delivery norms we want across the toolkit — they're worth lifting verbatim into our own playbook for any third-party-product work.

## How we'd use it ourselves

- Auto-invoked by the runtime on Supabase-related tasks. No manual call needed.
- The "verify against changelog before implementing" pattern generalizes — consider porting to `/claude/playbooks/` as a general principle for fast-moving SaaS-integration work.

## Install metadata

- Path on disk: `~/.claude/plugins/cache/claude-plugins-official/supabase/<plugin-version>/skills/supabase/`
- Skill version: 0.1.2 (independent of the plugin's 0.1.11)
