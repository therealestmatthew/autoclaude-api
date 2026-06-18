---
name: phase-8-3-dogfood-findings
title: "Phase 8.3 — dogfood findings (real-queue triage pass)"
phase: 8
status: done
created_at: 2026-06-17
updated_at: 2026-06-17
completed_at: 2026-06-17
related: [phase-8-3-write-back, phase-9-0-reviewer-agent]
---

# 8.3 dogfood findings — first real-queue triage pass

After shipping the 8.3 backend, I ran the API against the real
365-item queue and triaged five candidates (4 discards + 1 keep) via
`curl`. The session surfaced two real bugs in the write pipeline, both
caught on the very first call. The integration tests passed because
the fixture's `.gitignore` (`!*`) un-ignores everything, masking the
production reality where `/scout/queue/*.md` is gitignored.

This is exactly why dog-fooding matters. Test fixtures are
idealisations; production has gitignore.

## What the dogfood did

| Action     | Slug                                                       | Result       |
| ---------- | ---------------------------------------------------------- | ------------ |
| discard    | `amazon-and-the-white-house-ended-anthropic-s-fable`       | 500 → fixed → ok |
| discard    | `anthropic-flies-staff-to-d-c-to-clean-up-white-house-fight` | ok           |
| discard    | `trump-admin-blocks-foreign-access-to-anthropic-s-most-powerf` | ok        |
| discard    | `the-ai-price-war-is-here-piling-pressure-on-openai-and-anthr` | ok         |
| keep       | `anthropic-on-aws`                                         | 200 but no commit → fixed → orphan committed by hand |
| keep       | `claude-cookbooks`                                         | ok after fix |

Queue: 365 → 359 (−6). Catalog: 9 → 11 (+2).

## Bug 1 — `git add` fails on deleted gitignored paths

**Symptom:** the first `POST /queue/{slug}/triage` with
`action=discard` returned `500 Internal Server Error`.

**Cause:** `triage_discard` deletes the source file from disk, then
calls `git.commit(paths=[source])`. `git.commit` calls `git add --
<source>`. The source is gone AND gitignored (it was never tracked),
so git fails with `pathspec '...' did not match any files` (exit 128).

**Why the integration tests missed it:** the fixture's `.gitignore`
contains `!*` — it un-ignores everything to make sure the sample-repo
files are committed. So the fixture queue files ARE tracked, the
delete shows up as a tracked deletion, and `git add` succeeds.

**Fix:** `git add -A -- <path>` instead of `git add -- <path>` (the
`-A` flag picks up deletions); tolerate the "did not match" error
since gitignored paths are expected to not match.

## Bug 2 — `git add` is all-or-nothing on the command line

**Symptom:** after fixing bug 1, the `keep` action returned 200 but
no new commit appeared in `git log`. The new catalog file was on disk
but untracked.

**Cause:** my first fix passed both paths to a single `git add -A --
<source> <dest>`. When `<source>` (gitignored) failed with "did not
match", git stopped processing — `<dest>` (the new catalog file) was
never staged. My try/except swallowed the error and returned early,
so `is_anything_staged()` returned False, and `commit()` short-
circuited to "nothing to commit; return HEAD."

**Fix:** loop per-path, calling `git add -A -- <path>` once per path,
catching "did not match" per-path. Each path's outcome stands alone.

**Cost of the bug:** the dogfood produced an orphan file at
`catalog/anthropic-on-aws.md` — written to disk, but uncommitted and
inconsistent with its audit row (which claimed `commit_sha = HEAD`).
The audit row records "committed" because `is_anything_staged` said
False so `commit()` succeeded vacuously. The audit log lied.

## Plan corrections to fold back

### W1. The `commit()` "nothing-to-commit → return HEAD" branch is wrong for triage-keep / triage-merge

If the writer expects to produce a commit (anything with a tracked
target), a vacuous "nothing-staged" success means the writer's intent
didn't actually land. The audit log captures `commit_sha = previous
HEAD` and the row reads "committed" — but no commit was made.

**Correction:** `commit()` should know whether the caller *expects*
a commit. Triage-discard on a gitignored queue is fine with no
commit. Triage-keep / triage-merge / edit-* expect a commit and
should raise if nothing was staged. Add a `must_commit: bool` flag.

Folded into the 8.3 plan's failure-modes section.

### W2. Integration tests should mirror production gitignore

The fixture's `!*` was a sensible choice for 8.1 — we wanted every
file in the sample repo to be readable by the indexer regardless of
the parent repo's ignore rules. But for 8.3 write-back tests, the
fixture's permissive ignore hides production behaviour.

**Correction:** Two changes already landed:

- `test_triage_keep_with_gitignored_queue` and
  `test_triage_discard_with_gitignored_queue` add an extra
  `.gitignore` rule on top of the fixture's `!*` and `git rm --cached`
  the queue file, mimicking the main-repo state.

Long-term, a second fixture (`gitignored_fixture_repo`) modeled on
the main repo's gitignore is cleaner than per-test setup. Deferred to
when a third write-back test needs it.

### W3. Audit "committed" status is overloaded

A `committed` audit row can mean one of:

- "A new git commit was created" (edit, keep, merge with tracked target)
- "No commit was needed; the action succeeded" (discard on gitignored)
- (BEFORE FIX) "Nothing was staged so commit silently no-op'd" (bug)

After W1 lands, this collapses to the first two. But the first two
are still indistinguishable from the audit row alone — `commit_sha`
will point at HEAD-of-the-moment either way. Surface `commit_created:
bool` in the result column.

Folded into the 8.3 plan.

## What I did NOT find (good signal)

- Optimistic-lock 409s worked exactly as designed.
- The `safe_path` checks were never tripped.
- The atomic-write semantics held — no half-written files at any point.
- The audit-row pending → committed transition is solid; the orphan
  was the writer's mistake, not the audit's.
- `parse_frontmatter` / `render_document` round-tripped catalog and
  queue items without mangling YAML.

## What surprised me about the queue (orthogonal to bugs)

- **75% of the queue is news.** The first four I tried were all clear
  discards — pure news. This validates F3 in the v0 golden findings:
  the natural action distribution is heavily skewed.
- **Slug prefixes are awful.** Every queue file has a
  `2026-06-15-<slug>-<hash>.md` filename but the `name:` slug inside
  is just `<slug>`. The discard commits referenced the long filename;
  the audit `target_path` was the full path. Both correct, but it
  meant the commit-log readability is poor. Worth a thought when 9.0
  reviewer agent writes commit messages.
- **Catalog growth via UI feels good.** Adding two catalog items in
  five `curl` commands is faster than hand-editing markdown +
  staging + committing. Even via curl. The 8.3b frontend will be
  meaningfully better.

## Net result

Two bugs fixed, two regression tests added, two real catalog
entries (`anthropic-on-aws`, `claude-cookbooks`) — first dogfood-
driven growth of the catalog. The 8.3 plan picks up W1, W2, W3 as
deltas for the frontend session.
