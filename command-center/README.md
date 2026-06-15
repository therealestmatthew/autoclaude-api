# /command-center/

Orchestration and observability for the agentic system. Where we *watch* and *operate* everything.

## What lives here

- [threads/](threads/) — log of agentic threads (which agent, what task, what outcome). Mostly gitignored runtime data.
- [token-burn/](token-burn/) — token usage logs and rollup reports. Mostly gitignored.
- [runbooks/](runbooks/) — operator documentation: how to do specific operational tasks reliably.

## Phase 0 status

This directory is scaffold-only. No observability tooling exists yet — the structure is here so when Phase 7 (command-center build-out) lands, the home is obvious.

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
