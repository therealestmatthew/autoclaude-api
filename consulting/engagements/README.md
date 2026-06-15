# /consulting/engagements/

One folder per client engagement. The operational record of the business — scoping, status, retros, invoices-as-markdown.

## Folder naming

`<year>-<client-slug>/`

- `2026-acme-co/`
- `2026-acme-co-phase-2/` *(if a separate engagement with the same client)*

## What goes in an engagement folder

See `_template/` for the skeleton. At minimum:

- `README.md` with engagement frontmatter (client, status, dates, SOW link).
- `scoping.md` — initial scoping conversation, problem statement, in/out of scope.
- `status/` — weekly status reports (one file per week).
- `retro.md` — at engagement close.

Add as needed: `pricing-rationale.md`, `methodology.md` (tailored from `/consulting/methodologies/`), `handover.md`, etc.

## Privacy

Engagement folders may contain client-confidential material. Decide per engagement whether the folder should be tracked in this repo at all, or whether sensitive sub-files should be gitignored or moved to a private location. **There is no automatic protection here** — review before adding sensitive content.

## Why "engagement #0" for internal R&D

This very project (building the command center) is itself an engagement. Consider tracking it under `engagements/2026-internal-cc/` to eat your own dogfood on the engagement structure and produce a real example before any client work begins.
