---
name: phase-8-3-frontend-dogfood-findings
title: "Phase 8.3 frontend dogfood — findings"
phase: 8
status: done
created_at: 2026-06-18
updated_at: 2026-06-18
completed_at: 2026-06-18
related:
  - phase-8-3-write-back
  - phase-8-3-hardening-findings
  - phase-8-3b-triage-frontend
  - phase-9-0-reviewer-agent
---

# Phase 8.3 frontend dogfood — findings

This session ran an API-level dogfood of the 8.3 frontend surfaces
(catalog editor, triage panel, proposals inbox) and implemented the two
outstanding tasks from the 8.3 follow-up plan: G1 parent-rename cascade
(TASK 2) and two UX polishes (TASK 3). TASK 1's browser portion could not
be completed (no display available), so the dogfood below was conducted
entirely via curl + API assertions.

## What was tested

| # | Surface                             | Method          | Outcome               |
|---|-------------------------------------|-----------------|-----------------------|
| 1 | `GET /catalog/{slug}/raw`           | curl            | ✓ works               |
| 2 | `PUT /catalog/{slug}/frontmatter`   | curl            | ✓ commits, 200        |
| 3 | `scout:` key round-trip             | curl + file check | ✓ key survives save |
| 4 | `git log` shows new commit          | git             | ✓ commit_created=true |
| 5 | 409 version-mismatch                | curl            | ✓ fires correctly     |
| 6 | triage discard (gitignored queue)   | curl            | ✓ commit_created=false|
| 7 | triage merge → 404 target-not-found | curl            | ✓ fires correctly     |
| 8 | `GET /catalog/{slug}` for collision | curl            | ✓ 200/404 as expected |
| 9 | `GET /proposals`                    | curl            | ✓ renders (0 rows)    |

## What worked

### Round-trip safety (the key 8.3 contract)

The `/raw` route correctly returns all frontmatter keys including `scout:`,
`fingerprint:`, and other untyped fields. The `PUT /frontmatter` route
re-serializes only what was sent, so untyped keys survive when the editor
sends the full raw dict back. Confirmed: `scout:` key present after save.

### Error codes land as operator-facing vocabulary

- `409 {"code": "version-mismatch", "expected": "...", "current": "..."}` — clean
- `404 {"code": "target-not-found"}` — clean
- `409 {"code": "target-exists"}` — not re-tested (covered in prior dogfood)

All previously 500-surfacing errors are now first-class codes the UI can
branch on.

### commit_created on every write

Every response carries `commit_created: bool`. Discard of a gitignored
queue file returns `false` (no commit). Keep returns `true`. The audit row
matches. The reviewer agent will be able to detect silent no-ops vs real
commits.

## What was NOT tested (browser gaps)

The following surfaces require a browser and were not exercised:

- **Editor UX**: `/catalog/{slug}/edit` with FrontmatterForm + BodyEditor.
  The most likely friction is the JSON-editor textareas for `source`,
  `discovered`, and `relations` — raw textarea JSON is hostile for a
  non-technical operator.
- **TriagePanel UX**: The slug-collision check (TASK 3a) and merge
  autocomplete dropdown (TASK 3b) are code-complete but untested in a
  browser. Core interactions (debounce timing, dropdown close on outside
  click) can only be verified with a real browser.
- **Proposals UX**: `/proposals` filter form and accept/reject flow. The
  list renders (0 rows) but accept/reject require a reviewer-agent to
  seed proposals.
- **409 conflict banner + Reload button**: Requires editing a file between
  page load and save — only verifiable in a browser.

## G1 cascade (TASK 2) — landed this session

`triage_keep` now cascades parent-slug renames to catalog children. When
`target_slug != original_slug`:
- All `catalog/*.md` files with `relations.parent == original_slug` are
  rewritten and committed (one commit per child).
- All `scout/queue/*.md` files with the same condition are rewritten
  in-place (no commit — gitignored).
- The `TriageResponse` exposes `cascade: [{slug, new_parent}, ...]`.
- `TriagePanel` shows "also rewrote parent ref in N children: a, b, c"
  in the success state.
- Integration test (`test_triage_keep_with_rename_cascades_to_catalog_children`)
  passes: parent + 2 children fixture; triage_keep with rename; both
  children rewritten + committed.

## UX polishes (TASK 3) — landed this session

**TASK 3a — Slug-collision check (keep action)**:
- On `action=keep` with non-empty `targetSlug`, debounces 300ms then
  calls `GET /catalog/{slug}`.
- 200 → red "✗ slug taken — catalog/{slug}.md already exists" with link.
- 404 → green "✓ slug is free".
- Submit button disabled when slug is taken.

**TASK 3b — Catalog autocomplete (merge action)**:
- On `action=merge` with any input, debounces 300ms then calls
  `GET /catalog?q={text}&limit=20`.
- Renders dropdown below input with matching slug + title.
- Submit button disabled until the operator picks from the dropdown
  (prevents free-text 404 target-not-found surface).
- Dropdown closes on outside click via `pointerdown` listener.

## Friction observations (from code review)

### F1 — FrontmatterForm JSON textareas are raw

The three JSON-editor textareas (`source`, `discovered`, `relations`) are
bare `<textarea>` elements with no validation feedback until save. Typing
invalid JSON silently blocks the save (the `jsonOrNull` parser catches it
and the error shows only after clicking Save). For an operator familiar
with YAML/JSON this is workable; for anyone else it's a footgun.

**Recommendation**: In 8.3d or 8.4, replace with typed sub-forms for
`source` (url, type, authors, license) and `relations` (parent, related).
The `discovered` block is less frequently edited and can stay as JSON longer.

### F2 — BodyEditor is a raw textarea

The body is edited as plain markdown text with no preview. For short
bodies (under 20 lines) this is fine. For longer catalog entries with
GFM tables, a split-pane preview would help. Defer to 8.4.

### F3 — No diff preview before save

The editor shows the rendered markdown in a read view at `/catalog/{slug}`
but the edit form has no before/after diff. Operator must trust that the
save produced the intended change and verify via `/catalog/{slug}` after.
Low priority — git history is always available.

### F4 — version field shown as hex prefix (10 chars)

The version display in TriagePanel ("version ab3ce22c72") looks like a git
SHA to operators. Documenting in the runbook is sufficient; no code change
needed.

## Concrete recommendation

**Ship the 8.3 frontend as-is and move to Phase 9.0.**

Rationale:
- The backend contract is clean and battle-tested.
- The new UX polishes (TASK 3) resolve the two most common 4xx paths.
- The G1 cascade (TASK 2) closes the last known correctness gap.
- F1 (JSON textareas) is real friction but affects only the catalog editor,
  not the queue triage path. The triage flow is the high-frequency surface
  (350 candidates waiting). Fix F1 in 8.3d after the reviewer agent 
  (9.0) reduces the queue further.
- Browser testing is needed before declaring the UI fully verified, but
  the API contract that backs it is solid.

**Next session: Phase 9.0 reviewer agent.**

The session prompt is already written at
`/docs/plans/session_prompts/phase-9-0-reviewer-agent.md`.
