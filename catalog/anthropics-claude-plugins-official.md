---
name: anthropics-claude-plugins-official
kind: repo
title: "anthropics/claude-plugins-official"
status: adopted
quality: 5
tags: [claude-code, plugin-marketplace, anthropic]
source:
  type: github
  url: https://github.com/anthropics/claude-plugins-official
  authors: [anthropic]
  license: ""
discovered:
  via: manual
  on: 2026-06-14
relations:
  related: []
fingerprint: ""
created_at: 2026-06-14
updated_at: 2026-06-14
---

# anthropics/claude-plugins-official

Anthropic's official Claude Code plugin marketplace. Source of truth for first-party plugin distributions. Currently the only configured marketplace in our `~/.claude/settings.json`.

## Role in our stack

When Claude Code installs a plugin (e.g. `supabase@claude-plugins-official`), this repo is the place it pulls from. The marketplace contains plugin packages with their own `plugin.json` manifests; each released version gets cached locally under `~/.claude/plugins/cache/claude-plugins-official/<plugin>/<version>/`.

## Children we catalog

- [claude-plugin-supabase](claude-plugin-supabase.md) — the Supabase plugin distributed via this marketplace.

(More child plugins as we install them. Each plugin asset's `relations.parent` points back here only if we've adopted that plugin via this marketplace; alternates would go via the plugin's upstream repo.)

## Watch for

- New plugins added to the marketplace.
- Version bumps to plugins we've adopted (auto-updated by Claude Code; track via the cached `installed_plugins.json`).
