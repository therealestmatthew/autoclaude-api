# /docs/runbooks/

User-facing runbooks: how to *use* the autoclaude program in day-to-day work.

This is a different audience from [/command-center/runbooks/](../../command-center/runbooks/), which holds operator runbooks for the system itself (rotate credentials, restore state, investigate failed extractions). If a procedure is about *running the program to get a result*, it belongs here. If it's about *keeping the program healthy*, it belongs in command-center.

## Style

Same rules as command-center runbooks — imperative steps, verify after each step, troubleshooting section with failure modes you have actually seen. Runbooks rot; check `last_verified` before trusting one.

## What's here

- [scout-run.md](scout-run.md) — run the scout pipeline (single tick or per source) and review the queue.
