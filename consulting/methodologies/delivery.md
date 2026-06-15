---
name: delivery
title: "Delivery methodology"
applies_to:
  engagement_types: [feature-build, audit, rescue]
status: draft
version: 0.1
created_at: 2026-06-14
updated_at: 2026-06-14
---

# Delivery methodology

> **Status:** v0.1 draft — a placeholder structure to demonstrate the shape. Fill in from real engagement experience; don't pretend this is settled doctrine yet.

## Phases

1. **Sprint zero.** Discovery, scoping, environment setup. Output: a scoped statement of work + a working dev loop. Reference `/claude/playbooks/` for the technical setup steps.
2. **Build.** Time-boxed iterations with weekly status (`/consulting/templates/status-report.md`). Demo at end of each iteration.
3. **Stabilize.** Bug-fix, polish, documentation, handover.
4. **Close.** Retro (`/consulting/templates/retro.md`), case study (optional), invoice reconciliation.

## What separates this from "agile delivery"

- **Agentic toolkit is assumed.** We operate as a leveraged team; this changes capacity assumptions and pricing.
- **Catalog-driven learning.** Every engagement contributes back to `/catalog/` (sources of inspiration, patterns) and `/claude/` (skills, playbooks). The toolkit gets better per engagement.
- **Outcomes over outputs.** Status reports lead with outcome metrics, not story-point burn.

## Cadence

| Touchpoint        | Default cadence | Template                                        |
| ----------------- | --------------- | ----------------------------------------------- |
| Status report     | Weekly          | `/consulting/templates/status-report.md`        |
| Demo              | Bi-weekly       | (no template yet)                               |
| Retro             | End of phase    | `/consulting/templates/retro.md`                |
| Invoice           | Per SOW         | (no template yet)                               |

## Adapting per engagement

Copy the relevant sections into the engagement folder (`/consulting/engagements/<year>-<client>/methodology.md`) and tailor. The original here stays generic.
