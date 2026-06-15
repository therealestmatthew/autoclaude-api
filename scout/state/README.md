# /scout/state/

Per-source cursor and dedup state. One file per source slug.

## Why this directory is gitignored

State is per-machine runtime data. Committing it would cause merge conflicts on every scout run and leak nothing useful into history.

## State file shape (per source)

```json
{
  "source": "hackernews",
  "last_run_at": "2026-06-14T12:34:56Z",
  "cursor": {
    "last_seen_id": 39000000,
    "last_seen_timestamp": "2026-06-14T12:30:00Z"
  },
  "seen_fingerprints": [
    "sha256:abc...",
    "sha256:def..."
  ],
  "stats": {
    "runs": 17,
    "candidates_queued_total": 42,
    "errors_total": 0
  }
}
```

`seen_fingerprints` is bounded — the extractor should evict entries older than the dedup window (e.g., 30 days).

## Recovering from corruption

If a state file is bad, deleting it is safe — the next run re-queues from the beginning of the source's available history, which the dedup check against `/catalog/` will mostly filter out. Cost is one noisy review session.
