# /scout/sources/

Declarative source configs. One YAML per source. The scout agent loads everything in this directory and runs the matching extractor for each.

## Source file shape

```yaml
name: hackernews                       # slug, matches the file name
type: hackernews                       # which extractor handles it
enabled: true                          # toggle without deleting
poll_interval_minutes: 60              # how often the agent polls when running
match:                                 # how to decide if a hit is relevant
  any_of:
    - claude code
    - claude-code
    - anthropic sdk
    - mcp server
notes: "Optional human notes about what we watch this source for."
```

The `type` field maps to a parser in `/scout/extractors/`. Adding a new source *kind* means writing both a config here and an extractor.

## Current sources

- [hackernews.yaml](hackernews.yaml) — HN search + Algolia API.
- [lobsters.yaml](lobsters.yaml) — Lobste.rs newest/tagged RSS.
- [reddit.yaml](reddit.yaml) — selected subreddits.
- [awesome-lists.yaml](awesome-lists.yaml) — curated lists we re-scan periodically.
- [x-handles.yaml](x-handles.yaml) — specific accounts to track. *(Phase 5+, API access required.)*

## Adding a source

1. Create `<slug>.yaml` here.
2. If the `type` is new, add an extractor stub in `/scout/extractors/`.
3. Seed state in `/scout/state/<slug>.json` (or let the first run create it).
4. Test with `enabled: false`, then flip on.
