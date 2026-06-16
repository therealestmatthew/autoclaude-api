# Merge rules

How to decide what to do with a candidate in `/scout/queue/` when reviewing it against the existing `/catalog/`.

## Decision tree

```
For each queue candidate:

  1. Fingerprint or source.url matches an existing asset?
     └── YES → UPDATE existing asset:
                  - bump updated_at
                  - refresh source.* fields if changed
                  - add notes to body if our understanding has shifted
              DISCARD the queue file.

  2. High overlap (same title core, ≥2 shared tags, same primary author)?
     └── YES → PROPOSE MERGE:
                  - flag both candidate and existing asset for human review
                  - default action: merge candidate into existing (existing slug wins)
                  - record alternate URL in source.alternates if relevant

  3. Same artifact, different source surface (e.g., we found it on HN, but it
     also appears in an awesome-list we already catalogued)?
     └── YES → ADD ALTERNATE:
                  - append { type, url, discovered: {…} } to existing
                    source.alternates[]
              DISCARD the queue file.

  4. Related-but-distinct (same author, complementary tool; or supersedes an
     older entry)?
     └── YES → CREATE NEW asset and fill:
                  - relations.related[] with the existing slug(s), or
                  - relations.supersedes[] if it replaces an older asset
                    (also mark the old one status: archived)

  5. Genuinely new?
     └── YES → CREATE NEW asset. Set status: reviewed once written.
```

## Heuristics for "high overlap"

- Title Jaccard similarity > 0.6 on word tokens (post-stopword).
- Same primary author/org AND same `kind`.
- Same GitHub repo at different commits — always a merge, never a new asset.

These are guidance, not rules. When in doubt, propose merge and let the human decide. False positives waste a minute; false negatives create duplicates that pollute the catalog forever.

## What humans always own (Phase 0)

- Final decision on merge vs new vs discard.
- The body text — the *why we kept it* notes.
- The `quality:` score.
- Setting `status: adopted` (means we actually use this).

## What automation can own (later phases)

- Surfacing the candidate with a default action.
- Auto-archiving (status: archived) when source URL 404s for >30 days.
- Re-fingerprinting and bumping `updated_at` when source content changes.
- Suggesting tags from content.

Until that automation exists, all of these are manual.

## Automation (Phase 6 — `scout dedup`)

Phase 6 implements part of the decision tree above as `scout/dedup/`. The
engine is run automatically at the tail of `scout run` (skipped with
`--no-dedup`) and can be invoked on its own:

```sh
uv run scout dedup                    # all four passes
uv run scout dedup --pass identity    # one pass at a time (debug)
uv run scout dedup --dry-run          # report what would change; touch nothing
```

### What the engine does

| Pass | Trigger                                                       | Action                                                                                  |
| ---- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1    | Two items share exact `source.url` or `fingerprint`.          | Collapse to the catalog member (or earliest queue member; cross-kind prefers `repo`). Discard losers. |
| 2    | Two items share `canonical_github_url` (a subpath of a repo). | Same collapse logic as pass 1. Parent-child URL aliasing is detected and excluded.      |
| 3    | Two items in the same `(kind, primary_author)` bucket have title-token Jaccard ≥ 0.6. | Tag both with `mergeset_id: ms-<sha8>`; append a `## Merge proposal (auto)` body section recommending a target.  |
| 4    | Catalog asset has ≥3 consecutive 404s in `state/url-liveness.json` (first 404 >30d ago) **or** a non-empty `relations.supersedes` and `status: reviewed` for >30d. | Set `status: archived`, `archived_reason`, `archived_at`, bump `updated_at`. |

Cross-repo children with the same `child-name` (`<repo-a>--code-reviewer`
vs `<repo-b>--code-reviewer`) are NEVER collapsed — the parent scoping
already differentiates them.

### What the engine does NOT do

- **Promote anything to `/catalog/`.** Promotion is human-only forever.
- **Edit any `/catalog/` field other than `status`, `archived_reason`,
  `archived_at`, `updated_at`.** Even an incidental annotation (e.g.,
  `mergeset_id`) is reverted on write.
- **Apply merge proposals.** Pass 3 surfaces a recommendation; the human
  executes the merge (or rejects it).
- **Auto-merge sibling-child repos.** See above.

### Rejecting a merge proposal

When you don't agree with a `## Merge proposal (auto)` block, change the
header to `## Merge proposal (auto, rejected)`. On the next run, the engine
records the rejection in `/scout/state/merge-decisions.json` and will not
re-propose that mergeset.

The body section is for human readability; the JSONL ledger is the engine's
source of truth. If the two disagree the ledger wins.

### Idempotency contract

Running `scout dedup` twice in a row produces identical disk state on the
second run. This is enforced by `tests/unit/test_dedup_oscillation.py` and
`tests/integration/test_run_once_with_dedup.py`; a regression there blocks
merge.
