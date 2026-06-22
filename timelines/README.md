---
kind: readme
title: "Timelines"
---

# Timelines

Customizable timelines/calendars for any kind of planning that benefits from a date-shaped view.

Each `<slug>.md` here is one timeline. The entries live in frontmatter under `entries:`. The body is free-form notes about the timeline (purpose, owner, refresh cadence).

## When to add a new timeline

- Engagement / project plans (per client, per phase)
- Skill adoption roadmap (when each new tool goes live in the practice)
- Content release calendar (case studies, newsletters)
- Conference / training calendar
- Anything date-driven that doesn't fit into one of the structured DB-backed concepts (engagements, exports, etc.)

## Adding a new timeline

1. Copy `_template.md` to `<your-slug>.md`.
2. Fill in `title`, set `view: list` or `view: month`.
3. List entries under `entries:` — each entry needs a `title` and either a `date` (single day) or `start` / `end` (date range).
4. Optional: set `ref: <slug>` on an entry to link it to a catalog asset, engagement, or client.
5. Save — the indexer picks it up on the next sync; the `/timelines` page renders it.

## Entry schema

```yaml
entries:
  - title: "Acme kickoff workshop"
    date: 2026-07-01            # single-day entry
    type: milestone             # milestone | phase | deliverable | event
    color: emerald              # emerald | blue | amber | rose | violet | zinc
    ref: acme                   # optional — links to /catalog/acme or /clients/acme
    notes: "Boardroom A. Lead: MM."
  - title: "Discovery phase"
    start: 2026-07-02           # range entry — use start + end
    end: 2026-07-19
    type: phase
    color: blue
```
