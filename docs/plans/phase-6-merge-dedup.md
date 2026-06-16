---
name: phase-6-merge-dedup
title: "Phase 6 — Automated merge / dedup decisioning"
phase: 6
status: done
created_at: 2026-06-15
updated_at: 2026-06-15
completed_at: 2026-06-15
supersedes: []
superseded_by:
locked_decisions:
  - "Reviewer trust model: human-only for *promotion* to /catalog/. Phase 6 automates *triage and grouping*, not final decisions. Set in Phase 0/3/4."
  - "Auto-archive is allowed on objective signals (404 source for >30 days, supersedes chain). Auto-promote is not."
  - "Merge proposals are written to a queue file alongside the candidate, not applied destructively. Set here."
  - "Fingerprint scheme: sha256 over canonical bytes (file bytes for repo children; URL for top-level candidates). Set in Phase 4."
  - "Rejected merge proposals live in BOTH a body section (human override marker) and /scout/state/merge-decisions.json (engine source of truth); on conflict the JSONL ledger wins. Set here."
  - "Jaccard threshold for pass 3: 0.6 on title tokens. Intra-parent pairs use 0.9 to stay conservative. Tune from real data in a follow-up if precision/recall warrants. Set here."
  - "Queue 404s are NOT auto-discarded; pass 4 archives /catalog/ only. A queue 404 keeps the candidate (with a body note); the 404 itself is signal. Set here."
  - "Cross-kind dedup on URL is YES; the survivor preference is `repo` over `article` since repo carries Phase 4 extraction potential. Parent-child URL aliasing is detected and excluded. Set here."
  - "Sibling-child cross-repo dedup is NO by default. <repo-a>--<child> and <repo-b>--<child> are NOT duplicates — parent scoping already differentiates them. Pass 3 explicitly skips that pair. Set here."
  - "v1 is deterministic-rules-only. NO embedding / LLM-classifier paths. Re-examine in a later phase if deterministic rules leave clear gaps. Set here."
  - "Catalog allowlist: pass 4 may write only `status`, `archived_reason`, `archived_at`, `updated_at` on a /catalog/ asset. Identity-collapse against a catalog survivor may bump `updated_at` only. Every other in-memory mutation is reverted at write time. Set here."
  - "URL liveness (3-consecutive-404 tracking) lives in /scout/state/url-liveness.json and is populated OUT OF BAND, not by the dedup engine. The engine stays network-free so it remains a pure function of disk state. Wiring the liveness checker is left for Phase 7+. Set here."
---

# Phase 6 — Automated merge / dedup decisioning

## Goal

Take the queue from "every reviewer decision is a fresh judgement call" to
"every reviewer decision starts from a recommended action with evidence."
Implement the decision tree in `conventions/merge-rules.md` as code:
identical content collapses automatically, near-duplicates surface as
merge proposals, and the human still owns every final promotion to
`/catalog/`.

Output of the phase: review throughput goes from O(N candidates) to
O(N distinct artifacts), and the queue stops drowning under the volume
Phase 4 enabled (one repo can emit a dozen children; one popular tool
can appear on three awesome-lists, on HN, on Reddit, and as a child of
two parent repos).

## Non-goals (out of scope for this phase)

- **Auto-promoting candidates to `/catalog/`.** Human review remains the
  gate. We surface recommendations; the human still decides.
- **Quality scoring.** Phase 6 deduplicates; ranking by judged quality is
  later (or never — `quality:` may stay manual forever).
- **LLM-based dedup.** Embedding models / Claude-classifier paths are
  attractive but expensive and unreliable at our scale. v1 ships with
  deterministic rules (fingerprint, URL canonicalization, token overlap).
  Re-examine in a later phase if the deterministic rules leave clear gaps.
- **Cross-repo child collisions** (two repos each containing a
  `code-reviewer` agent). The slug already namespaces them by parent
  (`<repo-a>--code-reviewer` vs `<repo-b>--code-reviewer`), so they're
  not duplicates in the database sense. Whether they should *also* be
  flagged as conceptually-similar is Phase 7+ territory.
- **Auto-merging into `/catalog/`.** Merges between two queue files
  collapse them into one queue file; merges with an existing `/catalog/`
  asset surface as a *proposal* written into the queue file's body,
  never as a direct catalog edit.

## Constraints (inherited)

- **Human-in-the-loop for promotion.** Phase 0/1/3/4/5 doctrine. We do
  *not* loosen this. The automation operates on the queue side of the
  gate.
- **Sanitization on ingest.** Every Candidate already arrives sanitized.
  Phase 6 is allowed to read frontmatter and body as-is.
- **No bare XML / no untrusted-content execution.** Phase 6 doesn't fetch
  external content; it operates on what scout already queued. This rule
  is mostly trivially satisfied here.
- **Determinism over cleverness.** A dedup that changes its mind between
  runs is worse than no dedup. The rule set must be a pure function of
  the queue + catalog snapshot.

## Threat model (specific to this phase)

The dedup engine sees free-form text written by extractors. It is allowed
to *group* and *propose merges*, never to silently delete. The reviewer
must always be able to retrieve the original candidates, including ones
the engine considered duplicates.

Specifically:

- A grouping decision writes a `mergeset_id:` field into each member's
  frontmatter; it does not unlink files.
- A "supersedes" proposal writes a candidate body section; it does not
  edit the existing `/catalog/` asset.
- An auto-archive decision (objective 404, supersedes chain) writes
  `status: archived` and an `archived_reason:` and `archived_at:`. The
  file stays, the body keeps the explanation.

## Design

### Inputs

The dedup engine reads:

1. All files in `/scout/queue/*.md` (the candidates).
2. All files in `/catalog/*.md` (the existing assets).
3. The `seen_urls` map in `/scout/state/*.json` (for soft hints about
   which extractor surfaced the same URL twice).

It writes only to:

- The queue files (`mergeset_id:` annotations, proposal body sections).
- The catalog files (only for `status: archived` + `archived_reason:` /
  `archived_at:` on objective signals).
- A new `/scout/state/merge-decisions.json` ledger so the engine can
  detect oscillation (a candidate it grouped on tick N getting
  un-grouped on tick N+1 is a regression bell, not a feature).

### Decision pipeline

Four passes, in order. Each pass is a pure function of the prior state.

**Pass 1 — Identity collapse.**
Group by (fingerprint, source.url, canonical_github_url). All members of
a group with ≥2 entries collapse to the highest-quality representative:

- Prefer an existing `/catalog/` member over any queue member → discard
  queue members; bump the catalog member's `updated_at` if any queue
  member carries new info (later `discovered.on`, new `source.alternates`
  candidate URL).
- Among queue members, prefer the earliest `discovered.on`; the rest get
  deleted with a note in the surviving member's body listing the deleted
  filenames and reasons.

**Pass 2 — URL canonicalization.**
Apply `canonical_github_url` (already in `scout/_util.py`) and re-group.
A queue file pointing at
`https://github.com/foo/bar/blob/main/README.md` collapses into one
pointing at `https://github.com/foo/bar` if both are in the same scan.

**Pass 3 — Soft-overlap merge proposals.**
Group by (kind, primary author, title-token Jaccard ≥ 0.6). Members of a
group with ≥2 entries get a `mergeset_id: ms-<sha8>` annotation in
frontmatter and a proposal section appended to each member's body:

```markdown
## Merge proposal (auto)

This candidate appears to overlap with:
- [<other-slug>](other-queue-file.md) — Jaccard 0.74 on title tokens; same primary author.
- [<another-slug>](catalog/<another-slug>.md) — Jaccard 0.81; same `kind`; one shared tag.

**Recommended action:** merge into `<another-slug>` (existing catalog).
Add this candidate's `source.url` to `source.alternates[]` and discard
this queue file.

Auto-generated by Phase 6 dedup engine. Override by editing this section
to "Merge proposal (auto, rejected)" and the engine will not re-propose.
```

The reviewer either accepts (executes the merge by hand) or rejects (per
the override note). Rejections are recorded in
`/scout/state/merge-decisions.json` so future runs don't re-surface them.

**Pass 4 — Auto-archive on objective signals.**
Two triggers, both deterministic:

- A `/catalog/` asset whose `source.url` has 404'd on the last 3
  consecutive scout runs (tracked in source state). Engine sets
  `status: archived`, `archived_reason: source-url-404`,
  `archived_at: <today>`.
- A `/catalog/` asset whose `relations.supersedes` is non-empty and
  whose `status` is still `reviewed` after >30 days. Engine sets
  `status: archived`, `archived_reason: superseded`,
  `archived_at: <today>`.

Both archive moves are reversible — the file stays, only the status and
two new fields change.

### What the engine never does

- Edit any `/catalog/` asset's `name`, `kind`, `source.*`, `relations`,
  `quality`, or body. Only the four allowlisted status-change fields.
- Promote a queue candidate to `/catalog/`. That's still human-only.
- Delete a candidate when the merge proposal is rejected. Only after the
  reviewer applies the merge.

### Output: per-tick run record

The engine writes a JSONL record to
`/command-center/threads/<date>.jsonl` (same format as `scout run` and
`scout extract-repo`):

```json
{
  "thread_id": "dedup-<date>-<hhmmss>",
  "agent": "scout-dedup",
  "started_at": "...",
  "ended_at": "...",
  "outcome": "ok|partial",
  "summary": "identity=12 url=4 proposals=7 auto_archived=2",
  "stats": {
    "pass1_identity_collapse": 12,
    "pass2_url_canonicalize": 4,
    "pass3_merge_proposals": 7,
    "pass4_auto_archived": 2,
    "rejected_proposals_carried": 3
  }
}
```

### CLI surface

```
uv run scout dedup                        # run all four passes once
uv run scout dedup --pass identity        # one pass at a time (debug)
uv run scout dedup --dry-run              # report what would change; touch nothing
uv run scout dedup -v                     # verbose
```

The dedup pass also runs at the end of `scout run` (after Phase 4 repo
extraction) so the queue is always in its most-collapsed state when a
human shows up to review it. `scout run --no-dedup` skips that final pass.

## Failure modes & required handling

| Failure                                  | Action                                                                                |
| ---------------------------------------- | ------------------------------------------------------------------------------------- |
| Malformed queue / catalog frontmatter    | Skip that file; record in stats `errors`; continue. Never crash the whole run.        |
| Oscillation (member added to mergeset, removed, re-added on the same source data) | Hard error in stats; mark all members `mergeset_id: ms-conflict`; surface to reviewer. |
| Catalog member chosen as identity-collapse survivor but `status: archived` | Skip the collapse; record a warning. Archived items don't accumulate updates.  |
| 404-tracker missing data (fewer than 3 runs of evidence) | Skip pass 4 for that asset; nothing to do.                       |
| Two-pass interaction (pass 1 collapses A↔B, pass 3 tries to merge B with C) | Pass 3 uses the post-pass-1 state; B no longer exists. No conflict by design. |

## Code surface (rough)

New files:

```
scout/
  dedup/
    __init__.py
    engine.py             entry point: run_passes(queue_dir, catalog_dir, ...) -> Report
    fingerprint.py        sha256/canonical-URL helpers; thin wrappers around _util
    overlap.py            title-token Jaccard, author-match, kind-match
    archive.py            objective auto-archive rules
    cli.py                glue from scout.agent.cli to scout.dedup.engine
```

Updated files:

```
scout/agent/cli.py        + `dedup` subcommand + `--no-dedup` flag on `run`
scout/agent/runner.py     + invoke dedup engine at end of `run_once` (toggle-able)
conventions/merge-rules.md + section on automation: what the engine does and doesn't
docs/runbooks/scout-run.md + section on dedup + review-after-dedup workflow
```

New tests:

```
tests/unit/
  test_dedup_identity.py        pass 1: exact-fingerprint, exact-URL, canonical-URL
  test_dedup_overlap.py         pass 3: Jaccard math, author normalization, kind match
  test_dedup_archive.py         pass 4: 404 streak, supersedes-chain age
  test_dedup_oscillation.py     repeat-run idempotency under stable input
tests/integration/
  test_run_once_with_dedup.py   scout run with the dedup step wired; verify queue
                                  shrinks, catalog gains no spurious edits, thread
                                  log records the pass counts
tests/fixtures/dedup/
  exact-duplicate-pair/         two queue files with identical source.url
  near-duplicate-pair/          two queue files with high title overlap
  superseded-chain/             catalog asset that should auto-archive
  404-streak/                   catalog asset with 3-run 404 history in state
```

## Open questions to resolve during the session

1. **Where do rejected merge proposals live?** Body section overrides
   feel hand-wavy; a sidecar `merge-decisions.json` is more durable. *Recommendation: both — body section for human readability, JSONL ledger as the engine's source of truth. Conflict between them favors the JSONL.*
2. **Jaccard threshold.** 0.6 in `merge-rules.md` is a guess. *Recommendation: ship at 0.6; track precision/recall manually for a week; tune in a follow-up commit.*
3. **Auto-archive for queue files (not catalog).** A queue candidate
   whose URL 404s before the human reviews it — discard, or keep with
   `status: 404` so the reviewer sees the failure? *Recommendation: keep, with a body note. The 404 itself is signal.*
4. **Do we dedup across `kind`s?** A `repo` candidate and an `article`
   candidate could point at the same URL (the repo's home page). *Recommendation: yes, treat the URL as the identity key; collapse to the `repo` member because it carries Phase 4 extraction potential.*
5. **What about plugin/MCP children with the same name from two repos?**
   `repo-a--code-reviewer` and `repo-b--code-reviewer`. *Recommendation:
   no merge by default; the parent scoping is doing what it's supposed to
   do. Surface as `relations.related[]` proposal only if title Jaccard
   ≥ 0.8 *and* same primary author.*

Each open question gets answered in the commit; the answer moves into `locked_decisions:` on this plan's frontmatter at phase close.

## Task breakdown (suggested execution order)

| #  | Task                                                                                  | Parallelizable with |
| -- | ------------------------------------------------------------------------------------- | ------------------- |
| 1  | Update `conventions/merge-rules.md` with the automation section (what the engine does and doesn't). | 2 |
| 2  | Implement `scout/dedup/fingerprint.py` + `scout/dedup/overlap.py` (pure functions).   | 1                   |
| 3  | Implement `scout/dedup/engine.py` (orchestrates passes; returns a report).            | (depends on 2)      |
| 4  | Implement `scout/dedup/archive.py` (objective auto-archive rules).                    | 3                   |
| 5  | Wire `scout dedup` subcommand in `scout/agent/cli.py`.                                | 3                   |
| 6  | Wire dedup pass into `scout/agent/runner.py::run_once` (with `--no-dedup` toggle).    | 3                   |
| 7  | Unit tests: identity, overlap, archive, oscillation.                                  | 8                   |
| 8  | Integration test: `scout run` with dedup; verify queue shrinks; catalog edits limited to status. | 7 |
| 9  | Fixture sets (exact-duplicate-pair, near-duplicate-pair, superseded-chain, 404-streak). | 7, 8 (write first) |
| 10 | Update `docs/runbooks/scout-run.md` with dedup + review workflow.                     | 11                  |
| 11 | Quality gate: `uv run ruff check`, `uv run pytest`, `uv run pytest tests/integration`. | 12                 |
| 12 | Commit as one logical change. Flip plan status to `done`; finalise `locked_decisions:`. Rename session prompt to `phase-6-merge-dedup.done.md`. |

## Quality gate (must all pass before commit)

```sh
uv run ruff check scout/ tests/
uv run pytest -q
uv run pytest tests/integration -q
# Smoke (manual):
uv run scout dedup --dry-run
uv run scout run -v        # verify the dedup pass appears in the thread log
```

The dedup smoke must:

- Report ≥1 identity collapse on the current queue (the queue currently
  has near-duplicates from awesome-list + HN echoes; if it doesn't,
  something is wrong).
- Make no changes to `/catalog/` except `status: archived` on assets
  that meet the objective criteria.
- Be idempotent: running it twice in a row produces identical state on
  the second run.

## Commit message (template for task 12)

```
Phase 6: automated merge / dedup decisioning

- scout/dedup/: four-pass engine — identity collapse, URL canonicalization,
  soft-overlap merge proposals (Jaccard ≥ 0.6 on title tokens + same kind
  + same primary author), and objective auto-archive (404 streak,
  supersedes chain).
- scout/agent/cli.py: `scout dedup [--pass …] [--dry-run]` subcommand.
- scout/agent/runner.py: dedup pass runs at end of `scout run` by default;
  `--no-dedup` skips it.
- conventions/merge-rules.md: automation section — what the engine does
  and doesn't, and how to override merge proposals.
- Fixture sets exercise identity collapse, near-duplicate proposals, the
  superseded chain, and the 404 streak.
- docs/runbooks/scout-run.md: dedup + review-after-dedup workflow.
- docs/plans/phase-6-merge-dedup.md: status -> done; locked decisions
  finalised.
- docs/plans/session_prompts/phase-6-merge-dedup.done.md: archived.
```

## When this plan becomes stale

Status flips to `done` when the commit lands. From that point the plan
is read-only history. If the deterministic-rules approach proves
insufficient and we go embedding- or LLM-based, write a new plan that
`supersedes: [phase-6-merge-dedup]`.
