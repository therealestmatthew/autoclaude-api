---
name: anthropic
kind: org
title: "Anthropic"
status: adopted
quality: 5
tags: [anthropic, foundation-model, claude]
source:
  type: manual
  url: https://www.anthropic.com
  authors: []
  license: ""
  alternates:
    - type: github
      url: https://github.com/anthropics
discovered:
  via: manual
  on: 2026-06-14
relations:
  related: []
created_at: 2026-06-14
updated_at: 2026-06-14
---

# Anthropic

Maker of Claude (model family and Claude Code CLI). The publisher of the runtime everything in `/claude/` builds on, and the operator of the plugin marketplace (`anthropics/claude-plugins-official`) we currently consume from.

## Why this is in the catalog

Anthropic is the `source.authors` reference target for everything Anthropic-published — Claude Code itself, its built-in skills and agents, the plugin marketplace, and Anthropic blog posts/papers we catalog as `article`.

## Things to watch

- Claude Code releases (CLI, built-in skill/agent changes).
- Anthropic engineering and product blog posts.
- Model releases (Opus / Sonnet / Haiku) and their effect on our toolkit defaults.
- The official plugin marketplace at `anthropics/claude-plugins-official`.
