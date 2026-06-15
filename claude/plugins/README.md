# /claude/plugins/

Claude Code plugins — bundles that ship a coordinated set of skills, agents, and/or slash commands. One subdirectory per plugin.

## Layout per plugin

```
<slug>/
  README.md             purpose, what's bundled, how to install
  plugin.json           or whatever metadata the runtime expects
  skills/  agents/  commands/   per Claude Code plugin conventions
```

## When to make a plugin vs a loose skill

- A loose skill (`/claude/skills/<slug>/`) for one capability.
- A plugin (`/claude/plugins/<slug>/`) when several skills/agents/commands belong together and want to ship as a unit (e.g., a delivery toolkit, a code-review suite).

Plugins are a *packaging* decision, not a *capability* decision. Don't manufacture plugins just to organize; organize by directory inside `/claude/skills/` first.
