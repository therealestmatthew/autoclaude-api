---
name: supabase-postgres-best-practices-skill
kind: skill
title: "Skill: supabase-postgres-best-practices"
status: adopted
quality: 5
tags: [supabase, postgres, performance, skill, claude-code]
source:
  type: github
  url: https://github.com/supabase-community/supabase-plugin/tree/main/skills/supabase-postgres-best-practices
  authors: [supabase]
  license: MIT
discovered:
  via: manual
  on: 2026-06-14
relations:
  parent: claude-plugin-supabase
  related: [supabase-skill]
fingerprint: ""
created_at: 2026-06-14
updated_at: 2026-06-14

# Skill-specific
skill:
  version_installed: "1.1.1"
---

# Skill: supabase-postgres-best-practices

Postgres performance optimization guide structured as a Claude Code skill. Triggers when writing, reviewing, or optimizing Postgres queries, schema designs, or database configurations.

## Why this is high-quality

- Content is structured as **rules across 8 categories, prioritized by impact** — exactly the shape an LLM can apply without losing the prioritization signal.
- Each rule includes incorrect vs correct SQL examples and query-plan analysis. Not just prose advice.
- License is MIT — we can lift the patterns into our own skills/playbooks if useful, with attribution.

## How we'd use it ourselves

- Auto-invoked on Postgres tasks. No manual call needed.
- The "rules with incorrect/correct examples + query plans" structure is a strong template for any best-practices skill we author. Worth referencing when writing `/claude/skills/<our-best-practices>/`.

## Install metadata

- Path on disk: `~/.claude/plugins/cache/claude-plugins-official/supabase/<plugin-version>/skills/supabase-postgres-best-practices/`
- Skill version: 1.1.1 (independent of the plugin and the `supabase` skill)
