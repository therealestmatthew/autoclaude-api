# /claude/playbooks/

How to *use* agents, skills, and prompts effectively in delivery work. Playbooks are operating manuals — they sit above the artifacts and describe end-to-end workflows.

## What a playbook is

A markdown document that answers: "I have task X. How do I deliver it with our toolkit?"

Each playbook references the specific agents/skills/prompts it leverages and gives concrete sequencing.

## Frontmatter

```yaml
---
name: greenfield-feature-delivery
title: "Greenfield feature delivery with Claude Code"
context: "When the task is to add a feature to an existing codebase from scratch."
references:
  agents:   [planning-agent, code-review-agent]
  skills:   [verify, security-review]
  prompts:  [code-review-pr-summary]
created_at: 2026-06-14
updated_at: 2026-06-14
---
```

## Difference from /consulting/methodologies/

- `/consulting/methodologies/` — *how we sell and run the work* (discovery, estimation, status cadence). Business-facing.
- `/claude/playbooks/` — *how we technically deliver* with the agentic toolkit. Operator-facing.

A consulting methodology can reference a playbook ("during sprint zero, use the greenfield-feature-delivery playbook for the first feature"), but they live in different files because they answer different questions.
