# /command-center/

Orchestration and observability for the agentic system. Where we *watch* and *operate* everything.

## What lives here

- [threads/](threads/) — log of agentic threads (which agent, what task, what outcome). Mostly gitignored runtime data.
- [token-burn/](token-burn/) — token usage logs and rollup reports. Mostly gitignored.
- [runbooks/](runbooks/) — operator documentation: how to do specific operational tasks reliably.

## Running rollups (Phase 7)

The aggregator and renderer live in `scout/report/`. The operator
surface:

```sh
uv run scout report                       # today's rollup, printed
uv run scout report --week                # last 7 days
uv run scout report --since 2026-06-01    # custom window, ending today
uv run scout report --week --write        # also write to token-burn/reports/
```

Reports are deterministic — re-running over the same window produces a
byte-identical markdown file. `--write` is never auto-commit; once the
file lands, the operator inspects and commits by hand.

`scout doctor` runs static catalog integrity checks (orphan children,
broken supersedes, slug↔filename mismatch, required-field gaps,
stale-reviewed). `--fix` only normalizes filenames; nothing destructive
ever runs.

`scout check-urls` HEADs catalog `source.url`s and writes the liveness
state that pass 4 of the dedup engine consumes to decide auto-archive.
Same pass runs as a throttled tail step of `scout run`; opt out with
`--no-check-urls`.

See `docs/runbooks/scout-run.md` for the full surface.

## Mental model

```
agents do work    →    they emit thread events    →    /command-center/threads/
                                                            ↓
                                                     rollups + reports
                                                            ↓
                                                  /command-center/token-burn/

                       operators read runbooks  →   /command-center/runbooks/
                       to do anything operational
                       (kick off scout run, audit
                       a thread, rotate a secret)
```

## What goes in runbooks vs methodologies vs playbooks

- **`/command-center/runbooks/`** — how to operate *the autoclaude system itself*.
- **`/consulting/methodologies/`** — how to run *consulting engagements*.
- **`/claude/playbooks/`** — how to *deliver technical work* with the agentic toolkit.

Three different audiences, three different homes.
