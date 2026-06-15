# /command-center/threads/

Log of agentic threads — one entry per agent invocation (scout run, extraction job, etc.).

## Why mostly gitignored

Thread logs are high-volume runtime data. Per-machine, per-run, regenerated continually. Committing them would bury history. The directory and this README are tracked; `*.jsonl` and `*.log` are gitignored.

## Planned shape (Phase 7)

```jsonl
{"thread_id": "...", "agent": "scout", "started_at": "...", "ended_at": "...", "model": "claude-opus-4-7", "input_tokens": 1234, "output_tokens": 567, "tool_calls": 12, "outcome": "ok", "summary": "..."}
```

Append-only JSONL, one file per day (`YYYY-MM-DD.jsonl`).

## What to do with these

- Spot-check after every scout run: did anything fail silently?
- Aggregate into `/command-center/token-burn/` for weekly cost reports.
- Audit when something looks wrong (which thread produced the bad catalog entry?).
