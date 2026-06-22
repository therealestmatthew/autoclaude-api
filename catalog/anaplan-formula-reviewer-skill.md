---
name: anaplan-formula-reviewer-skill
kind: skill
title: "Skill: anaplan-formula-reviewer"
status: draft
quality: 3
tags: [anaplan, formulas, review, claude-code, stub]
delivery_function: [build, testing]
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
  related: [anaplan-hierarchy-auditor-skill]
  supersedes: []
fingerprint: ""
created_at: 2026-06-22
updated_at: 2026-06-22
---

# Skill: anaplan-formula-reviewer

Claude Code skill that reviews Anaplan line item formulas for correctness, performance, and adherence to Anaplan model-building standards.

## Triggers on

- Pasted Anaplan formulas (e.g., `LOOKUP`, `SUM`, `OFFSET`, `MOVINGSUM`)
- Module screenshots with formula bar visible
- Direct request: "review this formula"

## What it checks

- Correct use of dimension references (TIME vs. list members)
- Avoidance of common anti-patterns (`OFFSET` chains, deep `LOOKUP` nesting)
- Performance impact: cell count blow-ups, subset usage
- Suggests `SELECT:` formula variants when appropriate
- Validates aggregation method consistency

## How we'd use it

- Pair-program a model builder during build phase
- Run before promoting a module to UAT
- Ship in `/claude/skills/anaplan-formula-reviewer/` once authored

> **Status:** stub. The skill needs to be authored (`SKILL.md` + Anaplan formula reference docs).
