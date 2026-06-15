# /scout/agent/

The Python entry point that ties sources, extractors, state, and the queue together. **Empty in Phase 0.**

## Planned shape (Phase 2+)

Single-process Python (Claude Agent SDK) that, on a tick:

1. Loads enabled sources from `/scout/sources/`.
2. For each, loads cursor from `/scout/state/<source>.json`.
3. Dispatches to the matching extractor in `/scout/extractors/`.
4. For each candidate the extractor returns:
   - Compute fingerprint.
   - Dedup against state + `/catalog/` (any asset with matching `source.url` or `fingerprint`).
   - If new: write `/scout/queue/<scouted-at>-<slug>-<hash>.md` from the template.
5. Advance cursor in state.
6. Write a run record to `/command-center/threads/`.

## Why a thin Python core, not a framework

Sources are dumb. Extractors are isolated. The agent's only real responsibility is orchestration and dedup. Keep it under 300 lines; resist building a "platform."

## Entry points (to be added)

- `scout run --once`            — single tick, all enabled sources.
- `scout run --source <slug>`   — single source, useful for debugging.
- `scout run --watch`           — long-running loop.
- `scout review`                — interactive TUI over `/scout/queue/` (later).
