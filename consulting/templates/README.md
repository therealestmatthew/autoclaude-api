# /consulting/templates/

Fill-in-the-blank documents reused across engagements. Each template is a single `.md` file with frontmatter and `{{placeholder}}` markers.

## Files

- [proposal.md](proposal.md) — proposal document. *(Worked example.)*
- (planned) `sow.md` — statement of work.
- (planned) `status-report.md` — weekly status report.
- (planned) `retro.md` — engagement retrospective.

## Placeholder convention

Use `{{double-curly}}` markers. Common ones:

- `{{client}}` — client name.
- `{{date}}` — ISO date.
- `{{engagement_slug}}` — slug for the engagement (matches `/consulting/engagements/<year>-<slug>/`).
- `{{...}}` — anything else, named for what fills it.

Placeholders are documented in each template's frontmatter so future tooling can fill them programmatically.
