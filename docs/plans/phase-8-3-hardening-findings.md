---
name: phase-8-3-hardening-findings
title: "Phase 8.3 hardening — findings (extended dogfood, 12 candidates)"
phase: 8
status: done
created_at: 2026-06-17
updated_at: 2026-06-17
completed_at: 2026-06-17
related:
  - phase-8-3-hardening
  - phase-8-3-dogfood-findings
  - phase-9-0-reviewer-agent
---

# 8.3 hardening — findings from the extended dogfood

The hardening sub-phase closed the two correctness gaps W1 (audit
honesty) and W3 (`commit_created` in the result blob), then exercised
the backend against another 12 real queue candidates picked to hit
the cases the first dogfood missed (subdirectory URLs, slug renames,
parent-child cascade, famous-person discard, news cluster discards).

Headline: **the hardening fixes work**. Every triage in this pass
returned a `commit_created` that matched git reality, the audit row's
`result.commit_created` matched the response, the new 409
(`target-exists`) and 404 (`target-not-found`) translations landed,
and no `triage_*` call surfaced as a 500. Curl-driven triage is
**roughly tolerable** — the slug munging is the dominant friction.

## What the dogfood did

| #  | Action  | Slug (input)                                                  | Status | `commit_created` | New catalog file                                              |
| -- | ------- | ------------------------------------------------------------- | ------ | ---------------- | ------------------------------------------------------------- |
| 1  | keep    | `claude-api-fundamentals-course`                              | 200    | true             | `catalog/claude-api-fundamentals-course.md`                   |
| 2  | keep    | `use-the-claude-agent-sdk-with-your-claude-plan`              | 200    | true             | `catalog/use-the-claude-agent-sdk-with-your-claude-plan.md`   |
| 3  | keep    | `apple-foundation-models`                                     | 200    | true             | `catalog/apple-foundation-models.md`                          |
| 4  | keep+rename | `claude-code-as-a-daily-driver-…` → `claude-code-daily-driver-setup` | 200    | true             | `catalog/claude-code-daily-driver-setup.md`                   |
| 5  | keep+rename | `show-hn-skills-for-humanity-…` → `skills-for-humanity-s4h`        | 200    | true             | `catalog/skills-for-humanity-s4h.md`                          |
| 6  | keep    | `…—s4h-logic-check` (child of #5)                              | 200    | true             | `catalog/show-hn-skills-for-humanity-…—s4h-logic-check.md`   |
| 7  | discard | `antirez-on-x-i-believe-what-anthropic…` (famous person)      | 200    | **false**        | —                                                             |
| 8  | keep+rename | `show-hn-rotunda-…` → `rotunda-browser-for-agents`                | 200    | true             | `catalog/rotunda-browser-for-agents.md`                       |
| 9  | discard | `amazon-ceo-s-talks-with-u-s-officials-…`                      | 200    | **false**        | —                                                             |
| 10 | discard | `anthropic-sued-over-limits-on-its-200-a-month-ai-plans`       | 200    | **false**        | —                                                             |
| 11 | discard | `openai-considers-drastic-price-cuts-…`                        | 200    | **false**        | —                                                             |
| 12 | discard | `did-anthropic-ask-for-this`                                   | 200    | **false**        | —                                                             |
| 13 | keep (probe) | `anthropic-walks-back-…` → `anthropic` (collision)        | **409 target-exists** | —          | —                                                             |
| 14 | merge (probe) | `anthropic-walks-back-…` → `does-not-exist-anywhere`     | **404 target-not-found** | —      | —                                                             |

Queue 359 → 347 (−12). Catalog 13 → 20 (+7). Six discards landed
on gitignored queue files and (correctly) produced no commit; the
operator and any future reviewer agent can now tell that apart from
"the writer expected a commit and didn't get one" via the audit row.

## What worked

### W1 + W3 closed end-to-end

The new `commit_created` field is wired through:

- `git.commit()` returns `(sha, commit_created)`. `must_commit=True`
  (default) raises `NothingToCommit` on a no-op; `must_commit=False`
  returns `(HEAD, False)`. This is the load-bearing contract.
- `WriteResult` and `TriageResult` carry it. Wire models
  (`WriteResponse`, `TriageResponse`) expose it.
- The audit row's `result` blob includes it. The plan's example query
  (sqlite flavour):

  ```sql
  SELECT action, target_path FROM audit_event
  WHERE action LIKE 'triage%'
    AND json_extract(result, '$.commit_created') = 0;
  ```

  cleanly surfaces the 5 gitignored-discard rows from this session and
  excludes the 7 keep rows that moved git history. No false positives.

### New error translations

- `triage keep` with a `target_slug` already in `catalog/` returned
  **409** with `{"code": "target-exists"}` — exactly the contract.
- `triage merge` against a non-existent target returned **404** with
  `{"code": "target-not-found"}`.

Both used to bubble as 500s; both are now first-class operator-visible
states that the eventual UI / reviewer agent can branch on.

## Surprises (real friction)

### S1 — Slug double-dash on extracted children

The s4h-logic-check **child** asset (#6) was created by the scout's
parent-extractor with a slug containing a literal `--`:

```
show-hn-skills-for-humanity-171-structured-reasoning-skills--s4h-logic-check
```

That's the raw output of `<parent-slug>-<child-suffix>` with the
parent slug already ending in a meaningful token. The router accepts
it (the URL-segment routing handles the double dash without
ambiguity), but pasting that slug into curl is brutal. The renamed
parent (#5) was given `skills-for-humanity-s4h`; if the operator
forgets to rename children to match (`skills-for-humanity-s4h-logic-check`),
the catalog ends up with one human-readable parent + 170 ugly
children whose paths reference the *un-renamed* parent. **See S2.**

**Triggered:** F4 path. **Operator action:** rename children on keep,
or — better — wait for 8.3b to add a "rename pattern" affordance.

### S2 — Parent-child link breaks on rename

When #5 was renamed parent (`skills-for-humanity-s4h`), the child #6
file landed with:

```yaml
relations:
  parent: show-hn-skills-for-humanity-171-structured-reasoning-skills
```

— pointing at the **old** parent slug that no longer exists in
`catalog/`. The plan flagged this as out-of-scope ("Child's queue
file is unchanged; only parent moves"). Confirmed: triage_keep does
not cascade. This is fine for the dogfood and matches the plan's
explicit non-goal, but is a real backlog item:

- **Option A** (cheap): when `triage_keep` renames a candidate via
  `target_slug`, scan `/scout/queue/*.md` for any candidate whose
  `relations.parent == <old slug>` and rewrite to `<new slug>` in the
  queue. The operator keeps each child later; the rewrite already
  happened.
- **Option B** (correct): when the rewriter agent proposes a
  parent-rename it also proposes the dependent child rename as a
  bundled multi-proposal.

A is implementable today inside `triage_keep`; B waits for 9.0.
Holding the call until the reviewer-agent path is concrete.

### S3 — The `scout:` block carries through to the catalog file

Confirmed (already noted in the prior findings doc): the kept catalog
file has an entire `scout:` frontmatter block from the queue. That's
noise. Not in scope here; comes with the frontend's edit story per
the plan's non-goals.

### S4 — Curl ergonomics are the real story

The backend is fine. The friction is:

1. Slugs are long and easy to mistype (the s4h subtree).
2. Argument order in a shell helper is easy to swap — I sent
   `triage.sh <slug> keep <target>` once with `<target>` in the
   wrong position and got a 422 (`literal_error` on `action:`),
   which is the correct behaviour but felt like operator pilot
   error in a way a form wouldn't.
3. Getting the optimistic-lock token requires a GET first. A wrapper
   script trivialises it (my `/tmp/triage.sh` does the GET+POST in
   one), but without that script the operator pastes the version
   hash by hand.
4. No diff preview before commit. The operator has to trust that the
   writer is rewriting the frontmatter the way the dogfood plan
   promises.

None of these are 8.3-hardening bugs; they're 8.3b-frontend
requirements. The dogfood confirms that the **back end is ready**;
the **UI is what's missing**.

## Recommendation for the next session

**Go 8.3b frontend.**

The curl-driven path is *workable* but not pleasant. The dominant
friction is item-2 above — slug munging + lack of preview — and a
form solves it directly. The reviewer agent (9.0) on top of the
current backend would be impressive but it would multiply the same
friction (now the operator approves/rejects N proposals at the same
slug-paste rate). A modest UI in 8.3b reduces friction first, then
9.0 layers automated proposals on a smooth manual loop.

Concretely, 8.3b should ship:

- Queue list with one-click `keep / merge / discard` per row.
- A keep-rename input with a slug-collision check that surfaces 409
  *target-exists* before the operator submits.
- A merge-target picker that calls `/catalog?slug=` autocompletion,
  pre-empting 404 *target-not-found*.
- A diff preview pane for `edit_frontmatter` / `edit_body`.

That's the minimum that pays back the curl pain.

## Catalog growth

7 new catalog entries from this session:

- `catalog/claude-api-fundamentals-course.md`
- `catalog/use-the-claude-agent-sdk-with-your-claude-plan.md`
- `catalog/apple-foundation-models.md`
- `catalog/claude-code-daily-driver-setup.md`
- `catalog/skills-for-humanity-s4h.md`
- `catalog/show-hn-skills-for-humanity-171-structured-reasoning-skills--s4h-logic-check.md`
- `catalog/rotunda-browser-for-agents.md`

5 queue-only discards (no catalog impact):

- `antirez-on-x-…`, `amazon-ceo-…`, `anthropic-sued-…`,
  `openai-considers-…`, `did-anthropic-ask-for-this`.

## What this plan unlocks

- 8.3b frontend now has a stable backend contract to build against
  (`commit_created` on every write response, `target-exists` /
  `target-not-found` codes for the obvious failure modes).
- 9.0 reviewer agent's audit-honesty bar is real — a reviewer-agent
  triage that comes back with `commit_created: false` and no
  `target_path` is **provably a no-op discard**, not a silent
  failure. That's a precondition for auto-accept ramping.
- The parent-child cascade (S2) is the next correctness gap, but it
  can wait until either the rename surface or the reviewer-agent
  exists.
