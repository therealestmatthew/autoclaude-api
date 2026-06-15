# Contribution flow

How content moves from "found in the wild" to "part of our working toolkit."

```
                    [discovery sources]
                          │
                          ▼
                  /scout/queue/<id>.md       ← raw candidate, status: draft
                          │
                  human review (merge-rules.md)
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
          discard     merge into   /catalog/<slug>.md   ← reviewed asset
                      existing       │                    status: reviewed
                                     │
                              decide to use it
                                     │
                                     ▼
                          /claude/<area>/<slug>/   ← working copy
                                     │             status: adopted (in catalog)
                                     │
                              continued use, edits,
                              and our own additions
```

## Where to write, by intent

- **"I just found something interesting on HN."** → `/scout/queue/`. Don't pretend to evaluate it yet.
- **"I've looked at it and want to remember it."** → `/catalog/<slug>.md`, `status: reviewed`.
- **"We're actually using this in our toolkit."** → copy/adapt into `/claude/<area>/`, set the catalog asset's `status: adopted`. The catalog entry stays as origin record; the `/claude/` copy is the working artifact.
- **"This is internal IP, not from anywhere external."** → straight to the relevant `/claude/<area>/` or `/consulting/<area>/`. It does not need a catalog entry (catalog is for *collected* things).

## Pull-request norms

- One PR per logical change. A schema change is its own PR; bulk catalog additions are one PR per source-run.
- PR description names the catalog assets affected (new/updated/archived) so review is fast.
- Don't both add a new asset *and* refactor conventions in the same PR.

## Updating frontmatter

- Always bump `updated_at` when you change a catalog asset meaningfully.
- Never silently change `name` (the slug). Renames break links — use `supersedes:` and create a new asset instead.
- If you change `kind`, that's almost certainly a new asset. Old one becomes `status: archived`.
