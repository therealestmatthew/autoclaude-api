---
name: anaplan-hierarchy-auditor-skill
kind: skill
title: "Skill: anaplan-hierarchy-auditor"
status: draft
quality: 3
tags: [anaplan, hierarchy, validation, claude-code, stub]
delivery_function: [architecture, testing]
source:
  type: manual
  url: ""
  authors: [forge]
  license: ""
discovered:
  via: manual
  on: 2026-06-22
relations:
  parent:
  related: [anaplan-hierarchy-design-template, anaplan-formula-reviewer-skill]
  supersedes: []
fingerprint: ""
created_at: 2026-06-22
updated_at: 2026-06-22
---

# Skill: anaplan-hierarchy-auditor

Claude Code skill that audits a proposed Anaplan list/hierarchy design against best practices and the locked Hierarchy & Lists Design doc.

## Triggers on

- Pasted list structure (parent/child outline)
- A reference to a Hierarchy Design Doc in the repo
- Direct request: "audit this hierarchy"

## What it checks

- Subset count per list (warns if > 5)
- Numbered vs. named list appropriateness
- Time list configuration (calendar, fiscal offset)
- Parent/child cycles or orphan members
- Top-level "All" item presence where required by formulas
- Consistency between Data Hub source and downstream list ownership

## How we'd use it

- Run on the Hierarchy Design Doc before locking architecture
- Re-run mid-build when list changes are proposed (catch perf regressions early)
- Ship in `/claude/skills/anaplan-hierarchy-auditor/` once authored

> **Status:** stub. Skill body needs authoring.
