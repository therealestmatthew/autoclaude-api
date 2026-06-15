# /scout/queue/

Candidates surfaced by the scout, waiting for human review. Each candidate is a markdown file with the catalog frontmatter shape but `status: draft`.

## Why this directory is mostly gitignored

Queue items are raw, unreviewed signal. We don't want them in git history until a human has decided what to do with them — committing every scout run would pollute the log and capture content we may end up discarding. The directory structure is tracked (this README, `_template.md`); the per-run files are not.

Override the ignore on a per-file basis if you want a specific draft preserved across machines.

## Reviewing the queue

1. Open candidates in `/scout/queue/` (oldest first).
2. For each, follow the decision tree in `/conventions/merge-rules.md`.
3. Outcomes:
   - **Discard:** delete the file.
   - **Update existing:** edit the matching `/catalog/<slug>.md`, bump `updated_at`, delete the queue file.
   - **Merge:** combine into a single catalog asset (existing slug wins by default), delete the queue file.
   - **New:** move + rename to `/catalog/<final-slug>.md`, fill remaining fields, set `status: reviewed`.

## Candidate file shape

See `_template.md` in this directory.
