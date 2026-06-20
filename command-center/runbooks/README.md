# /command-center/runbooks/

How to operate the FT-AutoClaude system itself. Each runbook is a markdown document with a specific procedure that should be followable cold.

## Style

- **Imperative steps.** "Do X" not "we should do X."
- **Verify after each step.** "Run X. Expected output: Y. If you see Z, see troubleshooting."
- **Troubleshooting section** with the failure modes you've actually seen.
- **No prose ramble.** Runbooks are read by someone tired and stressed. Respect their time.

## Frontmatter

```yaml
---
name: rotate-github-pat
title: "Rotate the scout's GitHub PAT"
when_to_run: "Every 90 days, or immediately on suspected exposure."
last_used:
last_verified:
---
```

`last_verified` matters — runbooks rot. A runbook nobody has run in a year is suspect; mark it stale or re-verify before relying on it.

## Planned runbooks

None yet (Phase 0). Likely first ones once Phase 2+ lands:

- Run the scout once, by hand.
- Re-process a scout queue item after a bad initial review.
- Investigate a failed extraction.
- Rotate API credentials.
- Restore scout state from corruption.
