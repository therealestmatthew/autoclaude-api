---
name: phase-9-0-reviewer-agent
title: "Phase 9.0 — Reviewer agent (queue → catalog proposals)"
phase: 9
status: draft
created_at: 2026-06-17
updated_at: 2026-06-17
# 2026-06-17: amended in-place after v0 golden-set reconnaissance produced
# 7 findings (F1–F7) that change the design. See "Findings from v0
# reconnaissance" before reading the design.
completed_at:
supersedes: []
superseded_by:
related:
  - phase-6-merge-dedup
  - phase-7-observability
  - phase-8-3-write-back
locked_decisions: []
---

# Phase 9.0 — Reviewer agent

## Goal

Close the curation loop. We have 363 queue candidates and 8 catalog
assets — a 2% conversion rate after months of ingest. The bottleneck is
the human-in-the-loop review step. This milestone ships an LLM-driven
reviewer agent that proposes one of `keep` / `merge` / `discard` for
every queue candidate, with reasoning, surfaced to the operator through
the 8.3 proposal UI.

The success criterion is operational: after this phase ships, the
catalog grows weekly without manual data entry. An operator's job
becomes *approving* the reviewer's proposals rather than reading every
candidate from scratch.

The reviewer is the FIRST agent in the repo that emits the token-burn
schema fields Phase 7 laid down. The rollup column for `scout-reviewer`
finally lights up.

## Non-goals (out of scope for this milestone)

- **Auto-merge / auto-promote.** Every proposal still requires operator
  approval through 8.3. We do not write to `/catalog/` from the agent.
- **Semantic search (pgvector).** Context retrieval uses the existing
  substring search router. Vector embeddings are 9.x.
- **Multi-agent debate.** One reviewer. If we ever want a second opinion
  it's a separate proposal source — operator sees both, picks one.
- **Real-time dashboard for in-flight runs.** The runner is a CLI
  command; its progress is in JSONL. SSE is later (deferred from 8.4).
- **Generating frontmatter from scratch.** Queue candidates already have
  scout-extracted frontmatter. The reviewer suggests fixes but never
  hallucinates fields the candidate didn't expose.
- **Running on cloud / on a cron.** Local invocation only. Cloud is 8.5+.
- **Cost optimisation beyond the budget cap.** We pick Sonnet 4.6 by
  default and Opus 4.7 on escalation. We don't ship a fine-grained
  per-call cost model.

## Constraints (inherited and new)

Inherited:

- Markdown is canonical; the reviewer never writes catalog files.
- Promotion to `/catalog/` is human-only forever (the merge-rules
  convention). The reviewer proposes; the operator commits.
- Token-burn fields ride existing JSONL thread logs; rollup is unchanged.
- Phase 6 dedup output is the reviewer's first input — the engine has
  already collapsed duplicates and tagged mergesets.

New for 9.0:

- **One API key, locally held.** `ANTHROPIC_API_KEY` from env. No
  secrets in the repo, no cloud secret store.
- **Hard daily budget cap.** A spend tracker reads
  `command-center/token-burn/*.jsonl`, sums the day's cost, and refuses
  to invoke the model past the cap. Operator-overridable per-run.
- **Determinism via temperature 0 + cached prompts.** Two runs over an
  unchanged candidate set produce the same proposals.
- **Evals before ship.** A golden set of human-decided queue items.
  Reviewer must hit ≥80% action-match on it before the milestone ships.
  CI runs the eval; regressions block merge.

## Design

### 1. Where the agent lives

```
scout/reviewer/
  __init__.py
  agent.py            single-candidate review (sync entry point)
  context.py          fetch related catalog items via /search
  prompt.py           build the system + user prompts; cacheable
  schema.py           pydantic models for the reviewer's structured output
  budget.py           daily-spend cap + soft warnings
  runner.py           batch driver: enqueue N candidates, emit proposals
  cli.py              `scout review` subcommand
  evals/
    golden.jsonl      ~30 human-decided cases (manually curated; gitted)
    runner.py         score reviewer against golden; report drift
```

The reviewer is part of `scout/`, not `web/`. The web app *displays*
its output via the 8.3 proposal table; the agent itself is a pipeline
component like the dedup engine.

### 2. Trigger model

```sh
uv run scout review                       # batch: every queue item with no live proposal
uv run scout review -v                    # verbose: log every model turn
uv run scout review --slug <queue-slug>   # single candidate; useful for evals
uv run scout review --limit 25            # cap per invocation
uv run scout review --budget 5.00         # override budget; default reads env
uv run scout review --dry-run             # log proposals; don't write the DB
uv run scout review --model opus          # force Opus 4.7 instead of Sonnet 4.6 default
```

Wired into `scout run` as an optional tail step (`--review` flag, off by
default while we tune quality). When enabled the order is:

```
scout sources → queue → dedup → liveness → reviewer → rollup
```

No additional precondition. Phase 6 already runs as the queue is built
(via `scout run`'s tail step); the reviewer reads its output as context
but doesn't require it. The earlier F1 amendment about a hard precondition
is withdrawn — see the Findings section.

### 3. The prompt

Built dynamically per candidate. Shape:

```
SYSTEM:
You are the reviewer for the autoclaude catalog. Your job is to decide
what to do with each scout queue candidate. You produce a single
structured decision: keep / merge / discard, plus reasoning.

You do NOT write the catalog file. You do NOT decide quality scores.
You do NOT propose `status: adopted`. Those are operator decisions.

When you propose `merge`, you must name the target catalog slug.
When you propose `discard`, you must give a one-sentence reason.

Rules from /conventions/merge-rules.md (verbatim, cached):
<rules>

The asset schema fields (verbatim, cached):
<schema>

USER:
Candidate:
  slug: <slug>
  kind: <kind>
  title: <title>
  source: <source dict>
  body excerpt: <first 200 chars>

Nearby catalog assets (top 5 by substring search over title/tags/body):
  1. catalog/<slug>: <title>  (kind=<kind>, status=<status>, tags=<tags>)
     <one-line summary from existing body>
  2. ...

Phase 6 dedup hints:
  - mergeset_id: <id or "none">
  - duplicates_via_url: <slug or "none">

Phase 7 liveness:
  - source url status: <200 / 404 / unreachable>
  - 404_count: <n>

Output (structured JSON, schema:):
{
  "action": "keep" | "merge" | "discard",
  "target_slug": "<existing catalog slug if merge>",
  "confidence": 0..1,
  "rationale": "<2-4 sentence reasoning>",
  "suggested_edits": {
    "tags": [...],            // additive only; never removes existing
    "quality": null           // never set; left for operator
  }
}
```

The system prompt and the verbatim rules + schema are cached via
prompt-caching (`cache_control`). Each candidate-specific user message
is the only billed-fresh-tokens part of the call, so the cost-per-review
is dominated by output tokens.

### 4. Structured output

We use the Anthropic SDK's tool-calling pattern with a single tool
`emit_decision` whose JSON schema mirrors `Decision` (a pydantic model).
The agent is constrained to call exactly that tool. The tool's input is
the decision. This is more reliable than parsing free-form JSON.

```python
class Decision(BaseModel):
    action: Literal["keep", "merge", "discard"]
    scope: Literal["self", "parent-with-children"] = "self"  # F2
    target_slug: str | None = None              # required if action == "merge"
    suggested_slug: str | None = None           # F4 — rename target on keep
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    suggested_edits: dict | None = None
    flags: dict | None = None                   # F6, F7 — author_mismatch, url_target, etc.

    @model_validator(mode="after")
    def _merge_needs_target(self) -> Decision:
        if self.action == "merge" and not self.target_slug:
            raise ValueError("merge requires target_slug")
        return self
```

### 5. Budget cap

```python
# scout/reviewer/budget.py

@dataclass
class Budget:
    daily_usd: float
    spent_today_usd: float
    remaining_usd: float
    will_exceed: bool

def check_budget(date: date, cap: float) -> Budget:
    """Sum today's reviewer token-burn JSONL, return remaining."""
    ...

def estimate_call_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Model price table is data, not code (config in scout/reviewer/pricing.yaml)."""
    ...
```

Behaviour:

- Default cap: `$5/day` (configurable via `AUTOCLAUDE_REVIEWER_DAILY_BUDGET`).
- Pre-call: estimate cost from input length + a default output budget.
  If spent + estimate > cap, refuse the call. The runner logs and moves
  on.
- Post-call: record actual cost; if today's spend crosses 80% of the
  cap, emit a one-line warning.
- Runner exit: write a summary line to the JSONL with totals.

This piggybacks on the Phase 7 token-burn rollup. `scout report` will
show reviewer spend per day / per week without any additional code.

### 6. Model choice + escalation

- **Default:** `claude-sonnet-4-6`. Fast, cheap, more than capable for
  the bulk of decisions.
- **Escalation:** if Sonnet returns `confidence < 0.6`, re-run with
  `claude-opus-4-7` and take the Opus decision. Both runs are logged to
  the JSONL with `escalated_from: sonnet-4-6`.
- **Cap:** Opus escalation costs ~5× a Sonnet call. We cap at 20%
  escalation rate per run; above that we stop escalating and ship the
  low-confidence Sonnet decisions with `confidence < 0.6` flagged in the
  proposal. Operator triages those by hand.

### 7. Proposal write

The reviewer writes one `Proposal` row per candidate via the 8.3 DB
schema. Fields:

| Column          | Value                                                |
| --------------- | ---------------------------------------------------- |
| `source`        | `reviewer-agent`                                     |
| `target_path`   | `scout/queue/<slug>.md`                              |
| `target_bucket` | `queue`                                              |
| `action_kind`   | `keep` \| `merge` \| `discard`                       |
| `payload`       | `{target_slug?, suggested_edits?}`                   |
| `summary`       | first line of the rationale                          |
| `rationale`     | full rationale                                       |
| `confidence`    | 0..1                                                 |
| `status`        | `pending`                                            |

The 8.3 proposal-supersede sweep handles the case where a candidate gets
triaged by the operator before the reviewer runs (or where a candidate
already has a pending proposal — the new one replaces it; the old one
becomes `superseded`).

### 8. Evals

```
scout/reviewer/evals/
  golden.jsonl    ~30 lines, each: {candidate_slug, expected_action, expected_target_slug?, notes}
  runner.py       loads golden, runs reviewer, scores
```

We curate the golden set by hand: 10 clear keeps, 10 clear discards,
10 merges (with ambiguity baked in). Each entry includes the human's
rationale so we can compare not just action but reasoning.

Scoring (revised per F3 — action-match alone is gameable):

| Metric                                                          | Gate    | Notes |
| --------------------------------------------------------------- | ------- | ----- |
| `discard` precision (we discarded → operator agrees)            | ≥ 95%   | A false-discard wastes operator time but is recoverable. |
| `keep` precision (we kept → operator agrees)                    | ≥ 85%   | A false-keep pollutes the catalog forever. Hard floor. |
| `keep` recall (operator-kept items we also kept)                | ≥ 70%   | False-discard of a real asset is hard to recover; this floor is conservative. |
| Confidence calibration (Brier score on `confidence` vs correct) | ≤ 0.20  | High-confidence wrongs are worse than low-confidence wrongs. |
| `merge` precision + target-slug match                           | ≥ 70%   | Only gated once the golden set has ≥ 10 labeled merge examples. v0 has 0. |
| Action match (bare equality)                                    | report  | Kept as a summary; NOT a gate. |
| Rationale quality                                               | review  | Subjective; visual inspection during eval review. |

The eval runner is callable as `uv run scout review --evals`. CI (when
it lands) runs it on every PR that touches `scout/reviewer/`. A drop
below ANY gated metric fails the PR.

**Catalog-thinness escape valve:** if the golden set has fewer than 5
operator-labeled samples in a class, that class's gate is downgraded
to "report only" — the metric is computed and visible, but doesn't
block ship. This handles the realistic 9.0 launch state where the
catalog is too thin for clean merge examples to exist (see F3 in the
findings section). When the catalog grows past ~30 assets and the
golden set is expanded, the gates re-engage.

### 9. Failure modes & required handling

| Failure                                                  | Action                                                                  |
| -------------------------------------------------------- | ----------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY` unset                                | Reviewer refuses to start. Clear error pointing at the runbook.         |
| API call fails (network, 5xx, rate limit)                | Retry once after backoff; on second failure log + skip that candidate; continue with the rest. |
| Model returns malformed tool call                        | Log the candidate slug + raw response; skip; do not write a proposal.   |
| Budget cap hit                                           | Stop after the in-flight call; write a summary line; exit 0 (operator decides whether to raise the cap). |
| Candidate already has a `pending` proposal               | Skip (idempotent). Operator must `reject` or `accept` the existing one before a new run will replace it. |
| Target slug in a `merge` proposal doesn't exist in catalog | Mark the proposal `pending` but tag it `invalid_target`; operator sees the warning in the UI. |
| Reviewer's proposal conflicts with a Phase 6 dedup auto-archive | The proposal is annotated with the dedup state; UI shows both. Operator resolves. |

### 10. Tests

Unit:

```
tests/unit/reviewer/
  test_prompt.py          deterministic prompt assembly; cache markers in place
  test_schema.py          Decision validation; merge-target enforcement
  test_budget.py          today's spend math; cap exceeded; price table
  test_context.py         search-result formatting
```

Integration (these mock the Anthropic client at the SDK boundary):

```
tests/integration/reviewer/
  test_review_one.py            one candidate -> one proposal row
  test_review_batch.py          batch run with mixed outcomes
  test_escalation.py            Sonnet low-confidence triggers Opus
  test_budget_cap_halts_run.py  spend cap stops the runner mid-batch
  test_idempotent_re_run.py     second run on same input writes 0 new proposals
```

Evals (these hit the real API; gated behind `RUN_REVIEWER_EVALS=1`):

```
tests/evals/reviewer/
  test_golden.py          action-match ≥ 80%; target-slug ≥ 70%
```

### 11. Code surface

```
scout/reviewer/                  new
scout/agent/cli.py               + `review` subcommand
scout/agent/runner.py            + optional tail step (off by default)
pyproject.toml                   + anthropic SDK in `web` (since proposals land there)
                                 actually: new `[dependency-groups] reviewer`
command-center/runbooks/scout-review.md   new
docs/plans/phase-9-0-reviewer-agent.md    this file
```

The Anthropic SDK lives in a `reviewer` dep group, not in core, so
headless scout runs don't pull it.

## Findings from v0 reconnaissance (2026-06-17)

A reconnaissance pass labeled 17 of the 363 queue candidates as a v0
golden set (`scout/reviewer/evals/golden.jsonl`). The act of labeling
surfaced seven corrections to this plan. Each finding folds back into
the design above; reread the design assuming they apply.

### F1. ~~Phase 6 dedup is a prerequisite~~ (RETRACTED)

**Original observation (wrong):** The 363-item queue has zero
candidates with a `mergeset_id`, so Phase 6 hasn't run; the reviewer
should require it.

**Retraction (2026-06-17):** A dry-run of `scout dedup` returned
`identity=0 url=0 proposals=0 auto_archived=0`. The queue genuinely
has nothing for Phase 6 to collapse. What I read as "duplicates" —
governor parent/child, skills-for-humanity parent + ~30 children —
are `relations.parent` extractions that Phase 6 *correctly excludes*
from collapsing per merge-rules.md § "Parent-child URL aliasing is
detected and excluded."

The "dedup as precondition" amendment is withdrawn. The trigger
model stays as originally written:

```
scout sources → queue → dedup → liveness → reviewer → rollup
```

(The news cluster — 5+ near-duplicate Axios articles about
Anthropic D.C. politics — is also not a Phase 6 case: different URLs
and different primary authors put them in different Pass 3 buckets.
They survive as separate `discard` decisions, which is fine. Phase 6
isn't a deduper of conceptually-similar news.)

The deeper insight that the reviewer needs to handle parent-child
sets atomically is preserved in F2, where it actually belongs.

### F2. Parent-child sets are atomic decisions

**Observed:** Phase 4's repo extractor produces parent + children
candidates with `relations.parent` set. The keep/discard decision on
the parent implies the decision on its children — you cannot
`discard` a child whose parent is `keep` (orphans the child) or vice
versa. The merge-rules don't model this; the v0 golden set has two
parent-child pairs labeled `hard` for exactly this reason.

**Correction:** The reviewer batches parent-child sets. When the
runner sees a candidate with `relations.parent` set, it groups it
with its parent into a single review. The `Decision` schema gains:

```python
class Decision(BaseModel):
    action: Literal["keep", "merge", "discard"]
    scope: Literal["self", "parent-with-children"] = "self"
    # ...
```

A `scope: parent-with-children` decision writes one `Proposal` row
per member of the set, all with the same `decision_audit_id` and the
parent's `action`. The 8.3 triage UI accepts/rejects them as a batch.

### F3. The natural action distribution is heavily skewed

**Observed:** Roughly 75% of this queue is `discard` (news-shaped
articles about Anthropic D.C. politics, the Fable jailbreak, etc.).
An eval that just measures action-match is trivially gamed by
always-discard (gets ~75% without thinking).

**Correction:** Refine the eval to per-class precision/recall:

| Metric                                                  | Target | Why                                                 |
| ------------------------------------------------------- | ------ | --------------------------------------------------- |
| `discard` precision (of items we discard, % truly discardable) | ≥ 95%  | A false-discard wastes operator time but is recoverable. Still, 5% is a real annoyance. |
| `keep` precision (of items we keep, % truly keepable)   | ≥ 85%  | A false-keep pollutes the catalog forever. Hard floor. |
| `keep` recall (of truly keepable items, % we keep)      | ≥ 70%  | A false-discard of a real asset is lost forever unless the operator re-runs scout. |
| Confidence calibration (Brier score on `confidence`)    | ≤ 0.20 | High-confidence wrongs are worse than low-confidence wrongs. |

Drop the bare action-match metric from the ship gate. Keep it as a
reported summary.

**Sequencing implication:** the v0 golden set has 0 `merge` examples
(the catalog is too thin for clean merges to exist yet). The 30-item
target with 10 merges is not achievable until the catalog grows past
~30 assets. The ship gate uses whatever subset of the metrics has
enough labeled samples (currently: `discard` precision and `keep`
precision, both ≥ 5 samples each). Merge-quality gates land in a
9.x revision after the catalog grows.

### F4. Slugs need rename suggestions on `keep`

**Observed:** Several candidates have terrible scout-extracted slugs:
`show-hn-skills-for-humanity-171-structured-reasoning-skills`,
`governor-a-claude-code-plugin-to-reduce-token-context-waste`,
`claude-code-as-a-daily-driver-claude-md-skills-subagents-plu`. When
the reviewer proposes `keep`, the operator currently renames by hand
on promotion.

**Correction:** Add `suggested_slug` to the `Decision` schema. The
reviewer proposes a target slug per the naming convention; the 8.3
triage UI surfaces it as an editable field. The proposal's payload
carries it forward into the `triage keep` action which uses it as
the final `/catalog/<slug>.md` filename.

```python
class Decision(BaseModel):
    # ...
    suggested_slug: str | None = None  # rename target on keep
```

### F5. "Famous person, low content" tension

**Observed:** The antirez Twitter reaction is the entry every reviewer
will struggle on. The candidate is `kind: article` but the rule about
"load-bearing claims" applies; pure reaction has none. There's a case
for tracking notable people via `kind: person` separately.

**Correction:** The system prompt explicitly tells the reviewer:
*content* drives the decision, not the *author's reputation*. A
notable author writing a substantive analysis is a `keep`; the same
author writing a one-line reaction is a `discard`. People-tracking
(`kind: person`) is a separate workflow that the reviewer does NOT
propose — it's operator-curated.

### F6. Source URL subdirectory ambiguity

**Observed:** `claude-api-fundamentals-course` points to
`anthropics/courses/tree/master/anthropic_api_fundamentals`. Is the
catalog entry for the subdir, or for the parent repo? Catalog
convention doesn't say.

**Correction:** The reviewer flags subdirectory URLs (`/tree/`,
`/blob/`) and **never auto-picks** the parent. The proposal carries
`payload.url_target: "subdir" | "parent" | "unsure"` and the 8.3 UI
surfaces both options for the operator. The reviewer's bias when
unsure: keep the subdirectory URL the candidate has.

### F7. Author field is unreliable

**Observed:** `academic-research-skills-for-claude-code` has
`authors: [arnon]`, but "arnon" is the HN submitter — the repo owner
is `Imbad0202`. The scout extractor confuses the two.

**Correction:** The reviewer cross-checks `source.authors` against
the URL's hostname (for GitHub URLs, against the repo owner segment).
On mismatch, it flags `payload.author_mismatch: true` with a note.
The 8.3 UI prompts the operator to choose the correct authorship.

This is also a Phase 6 / scout fix candidate — but at the reviewer
layer we catch it cheaply.

## Open questions to resolve during the session

1. **What exactly goes into `nearby catalog assets`?** Top-5 by substring
   search seems shallow. We could also pull all assets sharing a tag.
   *Recommendation: top-5 substring + all assets with ≥2 shared tags,
   capped at 10. Vector embeddings replace this in 9.x.*
2. **Do we feed the dedup engine's `mergeset_id` as a strong signal or
   just context?** *Recommendation: strong signal — if a mergeset exists,
   default the reviewer's bias to `merge` and have it pick a target.
   This composes with Phase 6 instead of replicating it.*
3. **Should the reviewer also propose tag additions, or stay pure on
   keep/merge/discard?** *Recommendation: propose additive tag edits in
   `suggested_edits.tags`. Never proposes removals. The 8.3 UI surfaces
   the suggestion alongside the triage button; operator decides.*
4. **Where does the price table live?** *Recommendation: a YAML file at
   `scout/reviewer/pricing.yaml`, manually maintained per-model. Cheaper
   than calling the API to discover prices on every run.*
5. **Do we cache the system+rules+schema prompt across the batch?**
   *Recommendation: yes — Anthropic prompt caching with `cache_control:
   ephemeral`. The system+rules+schema block is ~2k tokens; caching cuts
   per-candidate input cost by ~70%.*
6. **Eval golden set: where do we get the 30 cases from?**
   *Recommendation: hand-pick from the 363 current queue items.
   The operator labels each with the action they'd take and a rationale;
   commit those decisions to `golden.jsonl`. Two hours of work, one-time.*

## Task breakdown

| #  | Task                                                                                              | Notes                                  |
| -- | ------------------------------------------------------------------------------------------------- | -------------------------------------- |
| 1  | Add `anthropic` SDK to a new `reviewer` dep group; document.                                      | Pulls in via `uv sync --group reviewer`. |
| 2  | `scout/reviewer/schema.py` (Decision + validators) + tests.                                       |                                        |
| 3  | `scout/reviewer/prompt.py` (system, rules, schema embed, cache markers) + tests.                  |                                        |
| 4  | `scout/reviewer/context.py` (search + tag-overlap retrieval) + tests.                             |                                        |
| 5  | `scout/reviewer/budget.py` (daily spend from JSONL; price table) + tests.                         |                                        |
| 6  | `scout/reviewer/agent.py` (one-candidate review; tool-call to emit_decision; retries).            |                                        |
| 7  | `scout/reviewer/runner.py` (batch driver; proposal writes; escalation; JSONL emit).               |                                        |
| 8  | `scout/reviewer/cli.py` + wire into `scout/agent/cli.py`.                                         |                                        |
| 9  | Optional tail step in `scout/agent/runner.py` (`--review`, default off).                          |                                        |
| 10 | Integration tests (SDK mocked) covering batch, escalation, budget cap, idempotency.               |                                        |
| 11 | Operator-review the v0 17-item draft golden set; bump `labeled_by` to `operator`; add 13 more entries to reach 30.  | v0 drafts already in repo from reconnaissance pass. Operator labor: ~2 hours. |
| 12 | Eval runner; document `uv run scout review --evals`.                                              |                                        |
| 13 | `/command-center/runbooks/scout-review.md`: how to run, how to interpret rollup, how to tune.     |                                        |
| 14 | `/conventions/merge-rules.md` update: "Phase 9 reviewer proposes; operator approves" section.     |                                        |
| 15 | CLAUDE.md + pyproject.toml + docs/plans/README.md (phase 9 entry).                                |                                        |
| 16 | Quality gate + dry-run smoke against 5 real queue items.                                          | No DB writes; eyeball the rationales.  |
| 17 | Live run (with budget cap): produce N pending proposals.                                          | Operator reviews via 8.3 UI.           |
| 18 | Commit. Mark plan `status: done`.                                                                  |                                        |

## Quality gate (must all pass before commit)

```sh
uv run ruff check scout/ web/ tests/ tools/
uv run pytest -q
uv run pytest tests/integration -q
uv run pytest tests/integration/reviewer -q

# Smoke (manual)
uv run scout review --dry-run --limit 5 -v
# Inspect 5 proposed decisions in the log. Confirm: action makes sense,
# rationale is grounded in the candidate, target_slug actually exists
# in the catalog when action == "merge".

# Eval (requires ANTHROPIC_API_KEY; ~$0.50)
RUN_REVIEWER_EVALS=1 uv run pytest tests/evals/reviewer -q
# Must report (per F3): discard_precision >= 0.95, keep_precision >= 0.85,
# keep_recall >= 0.70, brier <= 0.20. Merge gate is "report only" until
# the golden set has >= 10 operator-labeled merges.
```

## Production check (REQUIRED for 9.0)

After the dry-run smoke and eval pass:

1. Run a live, budget-capped batch: `uv run scout review --limit 25 --budget 1.00`.
2. Open the 8.3 web UI's proposals page; confirm 25 pending proposals appear,
   each with a coherent rationale.
3. Triage at least 5 by hand: 3 accepts, 2 rejects. Confirm the audit log
   captures each decision and the catalog/queue reflect the result.
4. Run `uv run scout report --day` and confirm the reviewer line lights up
   with non-zero tokens and the cost is under the cap.

## Commit message (template)

```
Phase 9.0: reviewer agent — proposals for queue → catalog

- scout/reviewer/: per-candidate review using Claude (Sonnet 4.6 default,
  Opus 4.7 escalation on low confidence). Structured tool-call output;
  prompt-cached system+rules+schema for cost.
- scout/reviewer/budget.py: daily spend cap (default $5) tracked from
  command-center/token-burn JSONL. Refuses calls past the cap.
- scout/reviewer/runner.py: batch driver writing Proposal rows via the
  8.3 schema. Idempotent on rerun.
- scout/reviewer/cli.py + scout/agent/cli.py: `scout review` subcommand
  (off by default in `scout run`).
- scout/reviewer/evals/: 30-item golden set; CI gate at action-match
  ≥ 80%, merge-target ≥ 70%.
- conventions/merge-rules.md: reviewer-proposes-operator-approves clause.
- command-center/runbooks/scout-review.md: operator playbook.
- pyproject.toml: anthropic SDK in `reviewer` dep group.
- docs/plans/phase-9-0-reviewer-agent.md: status -> done; locked
  decisions finalised.
```

## When this plan becomes stale

`status: active` while 9.0 implementation is in flight. Flips to `done`
when the commit lands and the production check passes. If a later phase
adds semantic-search context (9.x), upgrades to a different model
family, or moves the agent to a hosted runner, that's a successor plan
referencing this one — not an edit-in-place.
