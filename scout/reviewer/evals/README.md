---
name: scout-reviewer-evals-readme
title: "/scout/reviewer/evals/ — golden set for the reviewer agent"
kind: readme
status: stub
updated_at: 2026-06-17
---

# /scout/reviewer/evals/

Ground-truth labels for the queue → catalog reviewer agent (Phase 9.0).
The reviewer is scored against this set: `action` must match exactly; on
merges, `target_slug` must also match.

## Status: v0 reconnaissance, not the eval gate

The 17 entries currently in `golden.jsonl` are **drafts labeled by
Claude during the Phase 9.0 plan reconnaissance pass on 2026-06-17**.
They are NOT the final golden set; they exist so:

1. The shape of an eval entry is concrete (rather than an open question).
2. The Phase 9.0 implementation has something to wire `--evals` against.
3. The act of producing them surfaced real corrections to the plan
   (captured in the "Findings" section below).

**Before relying on the action-match metric for the 9.0 ship gate, the
operator must review every entry and re-label according to their own
judgment.** The `labeled_by` field is `claude-draft-2026-06-17` on
every row; operator-reviewed rows should bump it to `operator` and
update `labeled_at`. The eval runner (when it ships) should refuse to
score against rows whose `labeled_by` starts with `claude-draft-`
unless an explicit `--allow-draft-labels` flag is passed — that way the
CI gate can't accidentally tune the reviewer to agree with itself.

## Why this matters: the circular-reference problem

The reviewer agent is an LLM. If an LLM also labels the golden set, the
eval measures "does the agent agree with another LLM's judgment" —
likely from the same model family. That metric is uninformative about
whether the agent serves the *operator's* curation preferences. The
golden set's value is precisely that it encodes operator judgment that
the agent can't fake by being a competent LLM.

## Distribution of v0 entries (17 rows)

| Action  | Count | Notes                                                                  |
| ------- | ----- | ---------------------------------------------------------------------- |
| discard | 5     | 4 transient Anthropic-news articles + 1 famous-person Twitter reaction |
| keep    | 12    | Real tools / official Anthropic articles / Claude Code skill collections |
| merge   | 0     | This queue snapshot has no clean catalog-merge case (see findings)     |

The natural action distribution for this queue is heavily skewed toward
`discard`: roughly 70–80% of the 363 candidates are news-shaped
articles. An action-match metric that doesn't account for this is
trivially gamed by always-discard (gets ~75% without thinking). See
"Findings" for the metric refinement this surfaced.

## Findings (what producing this batch surfaced)

These are corrections to fold back into
`docs/plans/phase-9-0-reviewer-agent.md`. The plan reads them as the
delta between v0 and what 9.0 should actually ship.

### F1. ~~Phase 6 dedup is a prerequisite~~ (RETRACTED 2026-06-17)

**Original claim:** The 363-item queue has zero `mergeset_id`, so
Phase 6 hasn't run; the reviewer should require it.

**Retracted:** A subsequent dry-run (`scout dedup --dry-run`) showed
Phase 6 has nothing to collapse on this queue (`identity=0 url=0
proposals=0 auto_archived=0`). The apparent "duplicates" I saw —
governor parent/child, skills-for-humanity parent + 30+ children —
are NOT duplicates from Phase 6's standpoint. They're `relations.
parent` extractions from the Phase 4 repo walker, and Phase 6 § "Pass
2" explicitly excludes parent-child URL aliasing from collapsing.
The merge-rules and the engine are correct.

**What's still true:** the reviewer needs to handle parent-child sets
atomically (F2). But that's a `Decision.scope` concern, not a Phase 6
precondition. The 9.0 plan's "dedup as precondition" amendment should
be retracted; F2's scope-batching stands.

### F2. Parent-child sets are atomic decisions

Phase 4's repo extractor produces parent + children candidates with
`relations.parent` set. The keep/merge/discard decision on the parent
*implies* the decision on its children — you can't `discard` a
child whose parent you `keep` (you'd orphan the child) or vice versa.
The merge-rules don't model this. The reviewer should batch
parent-child sets into one decision; the proposal table needs a
`scope: parent-with-children` flag.

### F3. The natural action distribution is skewed; action-match isn't enough

~75% of this queue is `discard`. The eval needs a balanced metric:

- **Per-class precision/recall** instead of a single action-match
  number. Discard precision (do we keep things we should discard?) is
  weighted higher than keep precision in this regime — a false-keep
  pollutes the catalog forever; a false-discard wastes operator time
  but is recoverable.
- **Confidence-weighted scoring**: a Sonnet decision with `confidence
  > 0.9` that's wrong is much worse than one with `confidence < 0.5`
  that's wrong. The latter triggers Opus escalation; the former
  doesn't and pollutes the catalog directly.

### F4. Slugs need rename suggestions on `keep`

Several candidates have awful slugs that came from the scout's title
parser: `show-hn-skills-for-humanity-171-structured-reasoning-skills`,
`governor-a-claude-code-plugin-to-reduce-token-context-waste`. When
the reviewer proposes `keep`, it should also propose a target slug —
the operator currently has to rename by hand on promotion. Add
`suggested_slug` to the `Decision` schema.

### F5. The "famous person, low content" tension is real

The antirez Twitter reaction is the entry every reviewer will struggle
on. The candidate's `kind:` is `article` but the rule about
"load-bearing claims" applies; pure reaction has none. But there's a
case for tracking notable people via `kind: person` independently. The
prompt should explicitly tell the reviewer: *content* drives the
decision, not the *author's reputation*. A separate `person` workflow
should track who to follow.

### F6. Source URL points-to ambiguity

`claude-api-fundamentals-course` points to a subdirectory of
`anthropics/courses`. Is the catalog entry for the subdir, or for the
parent repo? Catalog convention doesn't say. The reviewer should flag
subdirectory URLs and let the operator decide — never auto-pick the
parent.

### F7. Author field is unreliable

`academic-research-skills-for-claude-code` has `authors: [arnon]` —
but "arnon" is the HN submitter, not the repo owner (`Imbad0202`).
The scout extractor confused the two. The reviewer should flag this
("HN-submitter recorded as author; repo owner is different") rather
than blindly copying the field forward.

## Schema (per JSONL line)

```json
{
  "candidate_slug": "<the queue file's `name:` field>",
  "candidate_path": "scout/queue/<filename>.md",
  "expected_action": "keep" | "merge" | "discard",
  "expected_target_slug": "<catalog-slug>" | null,   // required if action == "merge"
  "rationale": "1-3 sentence operator reasoning",
  "difficulty": "easy" | "medium" | "hard",
  "labeled_by": "operator" | "claude-draft-<YYYY-MM-DD>",
  "labeled_at": "2026-06-17",
  "context_at_label_time": {
    "kind": "<frontmatter kind>",
    "source_url": "<frontmatter source.url>",
    "discovered_via": "<frontmatter discovered.via>",
    "hn_score": null | <int>,
    "nearest_catalog_match": "<catalog slug>" | null,
    "phase6_mergeset_id": "<id>" | null,
    "edge_case": "<one-of-the-known-tags>" | null,
    "parent": "<parent slug>" | null,
    "child_count_in_queue": <int> | null
  }
}
```

The `context_at_label_time` block captures what the labeler saw so a
later eval run can tell whether the queue / catalog / dedup state has
shifted under the label. If `phase6_mergeset_id` was null at label time
but is non-null at eval time, the entry needs re-labeling (Phase 6 may
have moved the candidate into a mergeset whose decision overrides).

## When to expand the set

Target: 30 entries (10 keep, 10 discard, 10 merge), as the 9.0 plan
specifies. Current set is 17 (12 keep, 5 discard, 0 merge). To get to
30:

- Add 5 more obvious discards from the news cluster.
- Add 8 candidates with clean catalog-merge cases. **This requires a
  catalog with more than 8 assets** — the current catalog has so few
  entries that no queue candidate cleanly overlaps. The reasonable path
  is: get the reviewer producing keeps first, grow the catalog to ~30
  assets, *then* harvest the natural merge cases from a fresh queue.
- All 30 should be operator-labeled (`labeled_by: operator`).

This points at a sequencing decision: **the eval gate at 80% action-
match shouldn't block 9.0 shipping** if the catalog is too thin for the
gate to be meaningful. The 9.0 plan should be updated to reflect this.
