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
