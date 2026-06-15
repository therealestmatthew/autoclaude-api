---
name: phase-3-model-and-effort-recommendation
title: "Model & effort recommendation for Phase 3"
phase: 3
status: done
created_at: 2026-06-14
updated_at: 2026-06-15
completed_at: 2026-06-14
supersedes: []
superseded_by:
related: [phase-3-scout-v2-security]
locked_decisions:
  - "Phase 3 ran on Opus 4.7 (Sonnet 4.6 viable for mechanical sub-tasks delegated via subagents)."
notes: >
  Originated outside the repo (planning artefact named
  ~/.claude/plans/what-model-and-effort-tingly-flame.md). Imported on
  2026-06-15 to satisfy the planning-lineage rule in CLAUDE.md. Body
  unchanged from the original.
---

# Model & effort recommendation for Phase 3 completion

## Context

Phase 3 adds HN, Lobsters, and Reddit extractors to the scout pipeline, plus a security
baseline that retrofits all extractors. The full plan (serene-prancing-raven.md) has 16
tasks with locked design decisions. Most of the work is systematic; the one uncertain
area is Reddit's rate-limiting behavior (old.reddit.com fallback may be required).

## Recommendation

**Model: Opus 4.7**

Reasons:
1. Security-critical retrofitting — applying `_security.py` helpers correctly in three
   existing extractors requires careful reasoning about where URL validation and
   size-bounded reads must be called. A mistake here is a real vulnerability.
2. Reddit extractor is written from scratch (~150–180 lines) with no prior template in
   this codebase. Algolia and RSS extractors exist; Reddit's JSON API has different
   pagination and rate-limit behavior.
3. The session prompt explicitly flags "rough edges around Reddit's User-Agent / rate
   limits, which may force a switch to old.reddit.com" — a judgment call under
   uncertainty that benefits from stronger reasoning.
4. The plan calls for parallel subagents. The orchestrating session needs to coordinate
   correctly and not lose track of which tasks are done; Opus handles long multi-step
   sessions more reliably.

Sonnet 4.6 is viable for the mechanical sub-tasks (test fixture files, YAML flips,
runner registration) — Opus should orchestrate and delegate those to Sonnet subagents
if the harness supports mixed-model dispatch.

## Effort estimate

| Area | Complexity | Notes |
|---|---|---|
| Security retrofit (awesome-list, HN, Lobsters) | Low | 3–4 line swaps each; helpers already written |
| Reddit extractor (fresh) | Medium | JSON API, pagination cursor, User-Agent, possible old.reddit fallback |
| 6 new test files + fixtures | Low-Medium | Mechanical but must cover security paths |
| Runner registration + YAML flips | Low | Single-line additions |
| Quality gate + smoke tests | Low | `uv run ruff`, `pytest`, live calls |

**Total wall-clock estimate: 45–90 minutes** in a single Opus session using the
parallel-subagent execution order the plan prescribes.

## How to invoke

Use the session prompt at `/code/autoclaude/docs/plans/session_prompts/phase-3-completion.md`
verbatim. It already primes Opus with the locked decisions and out-of-scope guard rails.
Open a fresh Claude Code session (not this one) at `/code/autoclaude` and paste the
block inside the prompt file.
