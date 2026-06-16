# /command-center/token-burn/reports/

Committed rollup reports — output of `uv run scout report --write`.

## Convention

- One markdown file per period. Daily: `YYYY-MM-DD.md`. Weekly:
  `YYYY-MM-DD-week.md` where the date is the window start. Custom range:
  `YYYY-MM-DD-YYYY-MM-DD.md`.
- The renderer is deterministic — re-running `--write` over the same
  window produces a byte-identical file. Safe to re-run before commit.
- These files are tracked in git (everything else under
  `/command-center/token-burn/` is gitignored).

## Why the directory is named `token-burn/`

Historical artifact from the Phase 0 scaffold. The reports answer broader
"is the system healthy" questions, not only token burn; renaming is a
separate concern. For now, both report kinds (daily/weekly health
rollups, future per-(agent, model) token breakdowns) live here.
