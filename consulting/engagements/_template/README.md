---
client: client-slug
status: prospecting          # prospecting | active | paused | completed
started_on:                  # ISO date when work begins
ended_on:                    # ISO date when closed
sow_url:                     # link to signed SOW
primary_contact:             # name + role
---

# Engagement: {{client}}

> **This is a template.** Copy this directory to `/consulting/engagements/<year>-<client-slug>/` and fill it in.

## At a glance

- **What:** (One sentence — what we're doing for this client.)
- **Why:** (One sentence — the business reason it matters to them.)
- **Outcome:** (How we'll know this worked.)

## Files in this folder

- [scoping.md](scoping.md) — initial scoping output.
- [status/](status/) — one file per weekly status report.
- [retro.md](retro.md) — written at engagement close.

Optional, add when relevant:

- `pricing-rationale.md` — how this was priced and why.
- `methodology.md` — tailored from `/consulting/methodologies/delivery.md`.
- `handover.md` — close-out package for the client.

## Sensitivity

(Note here whether this folder is OK to track in the public-history repo or whether sensitive files should be gitignored / moved.)
