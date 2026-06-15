# /scout/

The discovery pipeline. Watches a set of external sources, queues candidates for review, and (once built) clones referenced GitHub repos to extract their contents into the catalog.

## Pipeline

```
 /scout/sources/       /scout/state/          /scout/queue/         /catalog/
 ─────────────         ──────────────         ─────────────         ─────────
 Source configs   →    Last-seen cursors  →   Candidate files   →   Reviewed
 (one YAML per         per source              (one md per find,    assets
  source: HN,           (last id seen,          with frontmatter,
  Lobsters, etc.)       last timestamp)         status: draft)
                                                       ↑
                                                       │
                                                /scout/agent/  ─→  /scout/extractors/
                                                Python entry          Per-source parsers
                                                point that ties       (HN API, Lobsters
                                                it all together       RSS, GitHub clone,
                                                                      etc.)
```

## Subdirs

- [sources/](sources/) — declarative configs for each discovery source.
- [state/](state/) — per-source cursors and dedup state (gitignored).
- [queue/](queue/) — candidate markdown files awaiting human review (mostly gitignored — see queue/README).
- [agent/](agent/) — Python agent: `types.py`, `runner.py`, `cli.py`. Exposes the `scout` console script.
- [extractors/](extractors/) — per-source parsers. Phase 3 shipped `hackernews.py`, `lobsters.py`, `reddit.py` alongside the Phase 2 `awesome_list.py`. All four use the security helpers in `scout/_security.py`. The Phase 4 `github-repo` extractor lands next.

## Design notes

- **GitHub is a target, not a discovery surface.** Sources are X, HN, Reddit, Lobsters, and awesome-lists. When a source mentions a GitHub URL, the repo extractor takes over.
- **Queue is intentionally lossy.** Better to queue too much and human-discard than to filter aggressively and miss things. The reviewer is the quality gate, not the scout.
- **State files matter.** Without per-source cursors, every run re-queues everything. State is the difference between "polls cleanly" and "drowns us."
- **One file per candidate.** Easier to review, easier to discard, easier to track.
