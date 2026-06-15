# /claude/prompts/

Reusable prompts and prompt templates not packaged as skills or agents. Standalone artifacts we paste into a chat, an API call, or a script.

## Layout

One `.md` file per prompt. Frontmatter declares intent and shape:

```yaml
---
name: code-review-pr-summary
title: "Summarize a PR for review handoff"
purpose: "Condense a long PR diff into a reviewer-friendly summary."
model: claude-opus-4-7        # or 'any'
expected_input: "diff text"
expected_output: "structured summary (markdown)"
tags: [code-review, summarization]
---

# Prompt body below the closing ---
```

## When prompts become skills

If a prompt is invoked often with the same scaffolding (input gathering, output validation), promote it to a skill in `/claude/skills/`. The prompt file can then be deleted or kept as a reference.
