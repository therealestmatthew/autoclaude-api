# /command-center/threads/

Log of agentic threads — one entry per agent invocation (scout run, extraction job, etc.).

## Why mostly gitignored

Thread logs are high-volume runtime data. Per-machine, per-run, regenerated continually. Committing them would bury history. The directory and this README are tracked; `*.jsonl` and `*.log` are gitignored.

## Shape

Append-only JSONL, one file per day (`YYYY-MM-DD.jsonl`).

**Required on every record:** `thread_id`, `agent`, `started_at`, `ended_at`,
`outcome` (`ok` | `partial` | `error`), `summary`. Agent-specific stats live
under `stats: {...}` — schema-free; the report aggregator reads what it
recognizes and ignores the rest.

**Optional token-burn fields** (Phase 7 schema; no agent emits these yet):

| Field                 | Type | Meaning                                    |
| --------------------- | ---- | ------------------------------------------ |
| `model`               | str  | Anthropic model ID (e.g. `claude-opus-4-7`)|
| `input_tokens`        | int  | Sum of input tokens for the run            |
| `output_tokens`       | int  | Sum of output tokens                       |
| `cache_read_tokens`   | int  | Prompt-cache reads                         |
| `cache_write_tokens`  | int  | Prompt-cache writes                        |
| `tool_calls`          | int  | Total tool invocations                     |

When the reviewer / curator agents (Phase 8+) land, they emit these
top-level keys and `scout report` rolls them up by `(agent, model)`
without any further code change.

Example:

```jsonl
{"thread_id": "scout-2026-06-15-100639", "agent": "scout", "started_at": "...", "ended_at": "...", "outcome": "ok", "summary": "queued=77 ...", "stats": {...}}
{"thread_id": "reviewer-2026-06-20-093000", "agent": "scout-reviewer", "model": "claude-opus-4-7", "input_tokens": 12345, "output_tokens": 678, "cache_read_tokens": 0, "cache_write_tokens": 0, "tool_calls": 5, "started_at": "...", "ended_at": "...", "outcome": "ok", "summary": "promoted=3 deferred=2"}
```

## What to do with these

- Spot-check after every scout run: did anything fail silently?
- Aggregate into `/command-center/token-burn/` for weekly cost reports.
- Audit when something looks wrong (which thread produced the bad catalog entry?).
