# Runbook: scout review (reviewer agent)

Last verified: 2026-06-19

## What this is

`scout review` runs the Phase 9.0 LLM reviewer agent over `scout/queue/` candidates
and creates pending proposals in the 8.3 proposal table. The operator then approves or
rejects them via the web UI (`/proposals`). The agent never writes to `/catalog/` directly.

## Prerequisites

1. **ANTHROPIC_API_KEY** set in your shell:
   ```sh
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

2. **API server running** for the live run (not needed for `--dry-run`):
   ```sh
   uv run autoclaude-api
   ```

3. **Reviewer deps installed**:
   ```sh
   uv sync --group reviewer
   ```

## Quick start

```sh
# Dry run: see what the agent would propose (no DB writes, no spend)
uv run scout review --dry-run --limit 10 -v

# Live run (default $5/day cap):
uv run scout review --limit 25

# Review specific candidates:
uv run scout review --slug claude-cookbooks anthropic-on-aws

# Run eval harness against the golden set (~$0.50):
uv run scout review --evals
```

## Budget cap

The reviewer tracks daily spend in `command-center/threads/<date>.jsonl` under the
`agent: "scout-reviewer"` key. The default cap is **$5/day**.

Override for one run:
```sh
uv run scout review --budget 10.00 --limit 50
```

Override persistently via env var:
```sh
export AUTOCLAUDE_REVIEWER_DAILY_BUDGET=10.00
```

When the cap is hit the runner stops cleanly (exit 0). Check the rollup:
```sh
uv run scout report
```

## Model selection

- Default: **claude-sonnet-4-6** (fast, cheap)
- Auto-escalation to **claude-opus-4-7** when Sonnet confidence < 0.6
- Escalation is capped at 20% of calls per run; above that, low-confidence Sonnet
  decisions are shipped with `confidence < 0.6` flagged in the proposal payload.
- Force a model: `--model opus` or `--model sonnet`

## Reviewing proposals in the UI

After the runner completes:

1. Open http://localhost:3000/proposals
2. Filter by `source: reviewer-agent` and `status: pending`
3. For each proposal, review the rationale and:
   - **Accept** → triggers the triage action (keep/merge/discard)
   - **Reject** → marks the proposal rejected; add a note

Accepted proposals run the same `triage_keep` / `triage_merge` / `triage_discard`
pipeline as manual triage. The audit log captures both the proposal decision and
the triage action.

## Clearing stale proposals

Proposals stay `pending` until explicitly accepted or rejected. To see all stale
pending proposals:

```sh
curl -s "http://localhost:8000/proposals?status=pending&source=reviewer-agent" | python3 -m json.tool
```

To reject a proposal via API (requires notes):
```sh
curl -X POST "http://localhost:8000/proposals/<id>/reject" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Rejected in bulk cleanup"}'
```

## Running the eval harness

The eval harness scores the reviewer against a hand-labeled golden set at
`scout/reviewer/evals/golden.jsonl` (17 items as of Phase 9.0).

```sh
# Via CLI:
uv run scout review --evals

# Via pytest (gate: must set env var):
RUN_REVIEWER_EVALS=1 uv run pytest tests/evals/reviewer/ -q -v
```

Gates that must pass before shipping a reviewer change:
- `discard` precision ≥ 0.95 (when ≥ 5 labeled samples)
- `keep` precision ≥ 0.85 (when ≥ 5 labeled samples)
- `keep` recall ≥ 0.70 (when ≥ 5 labeled samples)
- Brier score ≤ 0.20 (when ≥ 5 samples)
- `merge` precision ≥ 0.70 (only when ≥ 10 labeled merge examples — report-only in v0)

## Adding to the golden set

Edit `scout/reviewer/evals/golden.jsonl` (one JSON object per line). Required fields:

```json
{
  "candidate_slug": "my-queue-slug",
  "candidate_path": "scout/queue/2026-06-19-my-queue-slug-abc12345.md",
  "expected_action": "keep",
  "expected_target_slug": null,
  "rationale": "Why this is the right decision.",
  "difficulty": "easy|medium|hard",
  "labeled_by": "operator",
  "labeled_at": "2026-06-19"
}
```

After adding labeled items, run the evals to check if the gates still pass.

## Token burn rollup

The reviewer's token spend appears in `scout report` under the `scout-reviewer` agent
column. This is the same Phase 7 JSONL rollup that covers all scout agents.

```sh
uv run scout report          # today
uv run scout report --week   # last 7 days
```

## Pricing reference

Model prices are in `scout/reviewer/pricing.yaml`. Update this file when Anthropic
changes prices (no code change needed).

## Security

The reviewer agent:
- Never writes to `/catalog/`, `/scout/queue/`, or `/web/.data/` directly.
- Only calls the Anthropic API and the local proposals API.
- Honours the `ANTHROPIC_API_KEY` env var — never hardcodes credentials.
- Does not browse the web or spawn subprocesses.

See `/conventions/security.md` for the full security model.
