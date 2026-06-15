---
name: example-skill
kind: skill
title: "Example: a Claude Code skill"
status: reviewed
quality: 5
tags: [example, skill, verification]
source:
  type: github
  url: https://github.com/example-org/example-claude-tooling/tree/main/skills/verify
  authors: [example-org]
  license: MIT
discovered:
  via: awesome-claude-code
  on: 2026-06-14
  run_id: scout-2026-06-14-001
relations:
  parent: example-repo
  related: []
  supersedes: []
fingerprint: ""
created_at: 2026-06-14
updated_at: 2026-06-14
---

# example-skill

**This is an example, not a real catalog entry.**

A `skill` child of [example-repo](example-repo.md). Same parent/child shape as `example-agent`, different `kind`.

## Why we kept it

Compact, well-scoped Claude Code skill that does one thing well. Pattern to emulate when authoring our own skills in `/claude/skills/`.

## How we'd use it

If we adopted this skill, we'd:

1. Bump this asset's `status: adopted`.
2. Copy the skill into `/claude/skills/<our-slug>/` and adapt to our conventions.
3. Note any local modifications in the body below.
