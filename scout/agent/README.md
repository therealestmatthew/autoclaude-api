# /scout/agent/

The Python entry point that ties sources, extractors, state, and the queue together.

## Modules

- `types.py` — pydantic models for `Candidate`, `SourceState`, and per-source config models (`AwesomeListSource`, etc.).
- `runner.py` — `run_once()` orchestrator: loads sources, dispatches extractors, dedups against `/catalog/`, writes queue + state + thread log.
- `cli.py` — argparse entry point; installed as the `scout` console script.

## On a tick

1. Load enabled `*.yaml` from `/scout/sources/`.
2. For each, validate config into its pydantic model and load `/scout/state/<source>.json`.
3. Dispatch to the matching extractor in `/scout/extractors/`.
4. For each `Candidate` yielded:
   - Dedup against `/catalog/` (exact `source.url`, canonical GitHub URL, and `source.alternates[].url`).
   - If new: write `/scout/queue/<discovered_on>-<slug>-<hash>.md`.
5. Update cumulative stats; persist state.
6. Append a JSONL record to `/command-center/threads/<date>.jsonl`.

## Entry points

```sh
scout run                       # all enabled sources
scout run --source <slug>       # one source (matches filename stem in /scout/sources/)
scout run -v                    # verbose
```

`scout run --watch` is not implemented yet — see Phase 7 for the long-running operator story.

## Design constraint

Per the scout README: thin orchestration, no framework. `runner.py` is intentionally ~150 lines. Each new extractor registers in two tiny dicts at the top (`EXTRACTOR_REGISTRY`, `SOURCE_MODELS`) and that's the only place the runner changes per source.
