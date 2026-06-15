---
name: example-repo
kind: repo
title: "Example: a scouted GitHub repo with extracted children"
status: reviewed
quality: 4
tags: [example, claude-code, agents, skills]
source:
  type: github
  url: https://github.com/example-org/example-claude-tooling
  authors: [example-org]
  license: MIT
discovered:
  via: awesome-claude-code
  on: 2026-06-14
  run_id: scout-2026-06-14-001
relations:
  related: []
  supersedes: []
fingerprint: ""
created_at: 2026-06-14
updated_at: 2026-06-14
---

# example-repo

**This is an example, not a real catalog entry.** It exists to demonstrate the schema.

A scouted repo with two child assets: [example-agent](example-agent.md) (extracted as an `agent`) and [example-skill](example-skill.md) (extracted as a `skill`). Both set `relations.parent: example-repo` to point back here.

## Why we kept it

Demonstrates the parent/child pattern: one scouted repo, multiple catalog entries, one canonical source of provenance. The body of a `repo` asset is the place for our overall judgment of the repository — its philosophy, what's interesting about it, and what's worth our attention.

## Notes for reviewers

- A `repo` asset should always be created *first* when extracting children, so the children can point to it.
- The child assets carry their own source.url (the file or subfolder inside the repo) and the same authors/license unless they differ.
