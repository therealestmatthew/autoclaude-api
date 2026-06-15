# /command-center/token-burn/

Token usage tracking and rollup reports. The "are we spending money intelligently" view.

## Why mostly gitignored

Raw burn logs (`*.csv`, `*.jsonl`) are high-volume and regenerated. Rollup *reports* — weekly summaries, anomaly notes — can be committed if you want a historical record; place them in a `reports/` subdirectory when that exists.

## Planned shape (Phase 7)

Two layers:

1. **Raw:** per-thread token usage, sourced from `/command-center/threads/`.
2. **Rollup:** weekly summary by agent / by model / by purpose. Markdown reports committed.

## Questions this answers

- How much are we spending per scout run? Per extraction? Per engagement?
- Which agents are token-heavy and is the spend justified?
- Are we paying for context we don't use (cache misses)?
- Are there budget anomalies worth investigating?

## What it does not answer

- *Quality* of agent output — that's review, not burn.
- *Value* of the spend — that's a business question; the data here is an input to it, not the answer.
