---
name: example-agent
kind: agent
title: "Example: an agent extracted from a scouted repo"
status: reviewed
quality: 4
tags: [example, agents, code-review]
source:
  type: github
  url: https://github.com/example-org/example-claude-tooling/blob/main/agents/code-reviewer.md
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

# example-agent

**This is an example, not a real catalog entry.**

An `agent` child of [example-repo](example-repo.md). Notice the `relations.parent` field — that's how the graph is expressed without abandoning the flat polymorphic collection.

## Why we kept it

The agent illustrates a useful pattern (e.g., a code-review agent with specific tool restrictions and a structured output format). Worth referencing when designing our own.

## How we'd use it

- As a reference when writing our own code-review agent in `/claude/agents/`.
- The output format is reusable independently of the rest of the agent.

## Watch out for

- License compatibility before copying directly.
- Whether it depends on tools or MCP servers we haven't catalogued yet — if so, catalog those too.
