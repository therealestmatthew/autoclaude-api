---
name: phase-8-3-hardening
title: "Phase 8.3 — hardening + extended dogfood"
phase: 8
status: done
created_at: 2026-06-17
updated_at: 2026-06-17
completed_at: 2026-06-17
supersedes: []
superseded_by:
related:
  - phase-8-web-command-center
  - phase-8-3-write-back
  - phase-8-3-dogfood-findings
  - phase-8-3-hardening-findings
  - phase-9-0-reviewer-agent
locked_decisions:
  - "`git.commit()` returns `(sha, commit_created)`; `must_commit=True` is the default. `triage_discard` is the only writer that passes `must_commit=False`."
  - "Every write-back response and audit `result` blob carries `commit_created: bool`. Reviewers (operator or agent) read it to tell intentional no-ops apart from silent failures."
  - "Triage routing translates `FileExistsError` → 409 `target-exists` and `FileNotFoundError` → 404 `target-not-found`."
  - "Next session goes 8.3b frontend (operator UI). The curl loop works but slug munging + lack of diff preview are the gating friction — see findings."
---

# Phase 8.3 hardening — close the correctness gap + extend the dogfood

## Goal

The 8.3 dogfood pass (commit `9bfcc71`) shipped two bug fixes and a
findings doc that named three deltas — W1, W2, W3 — that the dogfood
surfaced about the backend. This sub-phase closes the two that are
correctness gaps (W1 audit-honesty, W3 commit_created) and validates
the fixes by exercising 8.3 against another 10–15 real queue
candidates, picked to hit the cases the first dogfood couldn't (the
parent-child cascade, the famous-person low-content discard, slug
renames on `keep`).

Output: a backend with no known latent correctness gaps, a catalog
that has grown from another curation pass, and a clear recommendation
about which fork to take next — 8.3b frontend or 9.0 reviewer agent.

## Non-goals (out of scope for this sub-phase)

- **8.3b frontend.** Components, pages, form validation — the next
  session after this one.
- **9.0 reviewer agent.** Separate fork; needs `ANTHROPIC_API_KEY`.
- **W2 (production-gitignore fixture).** The two regression tests
  that landed in `9bfcc71` cover the gitignored case adequately for
  now. Cleaner fixture is deferred until a third write-back test
  needs it.
- **Schema changes to `Asset` / `Proposal`.** Anything beyond a
  `commit_created` field on the result blob is out.
- **Frontmatter cleanup on `keep`.** The current keep flow carries
  the scout's `scout:` block through to the catalog file. That's
  noise on the catalog entry. Fix is operator-flagged (see
  `docs/plans/phase-8-3-dogfood-findings.md` § "Net result"), but
  not in scope here — comes with the frontend's edit story.

## Constraints (inherited and new)

Inherited from 8.3:

- Markdown is canonical; the DB is a derived index.
- Routers don't open files / DB sessions directly.
- Every write produces a single git commit OR no commit at all — but
  the audit row reflects reality either way.
- Optimistic locking via `version` stays.

New for this sub-phase:

- **Audit-row honesty.** An audit row whose `status: committed` must
  be accompanied by a `result.commit_created: bool` that's true iff
  a new SHA was actually produced. The bug in `9bfcc71` was caught
  because the audit row claimed `commit_sha = <previous HEAD>` and
  said `committed` even though no commit was made. That gap closes
  here.
- **No-op success has a real shape.** `triage_discard` of a
  gitignored queue file is genuine success without a commit. The
  result must distinguish that from the bug-class "the writer
  expected a commit and didn't get one." A `must_commit` flag at the
  git layer enforces the difference.

## Design

### 1. `must_commit` in `git.commit()`

```python
class NothingToCommit(RuntimeError):
    """Raised when commit() was called with `must_commit=True` and the
    add step left nothing staged. Distinguishes 'this is a real
    failure' from 'this was an intentional no-op'."""


def commit(
    repo_root: Path,
    *,
    paths: Iterable[Path],
    message: str,
    must_commit: bool = True,
    author_name: str | None = None,
    author_email: str | None = None,
) -> tuple[str, bool]:
    """Stage and commit. Returns (sha, commit_created).

    If `must_commit=True` and nothing was staged, raises
    NothingToCommit. The writer that expected a commit didn't get
    one; this is a bug or a real conflict, not a no-op.

    If `must_commit=False` and nothing was staged, returns
    (current HEAD, False). This is the `triage_discard` path: the
    queue file was gitignored, so the delete doesn't produce a
    commit. The caller's intent was always 'remove from the queue';
    no git commit was promised.
    """
```

Callers update accordingly:

| Caller            | `must_commit` | Why                                          |
| ----------------- | ------------- | -------------------------------------------- |
| `edit_full`       | `True`        | Always modifies a tracked file               |
| `edit_frontmatter`| `True`        | Same                                         |
| `edit_body`       | `True`        | Same                                         |
| `triage_keep`     | `True`        | New catalog file MUST be committed           |
| `triage_merge`    | `True`        | Modified catalog target MUST be committed    |
| `triage_discard`  | `False`       | Queue file is typically gitignored           |

### 2. `commit_created` in result types

```python
@dataclass(frozen=True)
class WriteResult:
    path: str
    commit_sha: str
    new_version: str
    commit_created: bool   # NEW


@dataclass(frozen=True)
class TriageResult:
    action: str
    source_path: str
    target_path: str | None
    commit_sha: str
    new_version: str | None
    commit_created: bool   # NEW
```

Pydantic wire shapes mirror this:

```python
class WriteResponse(BaseModel):
    path: str
    commit_sha: str
    new_version: str
    audit_id: str
    commit_created: bool = True   # NEW; default True for back-compat


class TriageResponse(BaseModel):
    action: Literal["keep", "merge", "discard"]
    source_path: str
    target_path: str | None
    commit_sha: str
    new_version: str | None
    audit_id: str
    commit_created: bool = True   # NEW
```

TS mirror in `api-types.ts` follows.

### 3. Audit row records reality

The audit's `result` dict gets the same field:

```python
audit.commit(
    result={
        "commit_sha": result.commit_sha,
        "commit_created": result.commit_created,
        "target_path": result.target_path,
    }
)
```

A query like `SELECT * FROM audit_event WHERE action LIKE 'triage%'
AND result->>'commit_created' = 'false'` cleanly surfaces the
"discard of an ignored file" cases vs. anything that actually moved
the git history.

### 4. Extended dogfood pass

Pick 10–15 candidates from the v0 golden set hitting the cases the
first dogfood missed:

| Case                              | Slug                                        | Expected | Why pick this one |
| --------------------------------- | ------------------------------------------- | -------- | ----------------- |
| Easy keep, official Anthropic     | `claude-api-fundamentals-course`            | keep     | Tests subdirectory URL handling (F6) |
| Easy keep, official Anthropic     | `use-the-claude-agent-sdk-with-your-claude-plan` | keep | Smoke an article-shaped keep |
| Easy keep, Anthropic platform doc | `apple-foundation-models`                   | keep     | Same                  |
| Medium keep, slug rename          | `claude-code-as-a-daily-driver-claude-md-skills-subagents-plu` | keep + slug-rename | Tests the `target_slug` rename on `keep` (F4) |
| Hard keep, parent of many         | `show-hn-skills-for-humanity-171-structured-reasoning-skills` | keep | Tests what happens when we keep a parent with 30+ children in queue (F2) |
| Hard keep, one child of above     | `show-hn-skills-for-humanity-171-...-s4h-logic-check` | keep | After parent is kept; does the child keep work cleanly or does it need parent context? |
| Hard discard, famous person       | `antirez-on-x-...`                          | discard  | Tests the "famous-person low-content" rule (F5) |
| Medium keep, low-traction         | `show-hn-rotunda-a-browser-built-for-agents-with-simulated-ty` | keep | Tests a borderline keep |
| Easy discard, news cluster        | (pick 2–3 from the un-discarded news)       | discard  | Volume                |

After each triage, capture:

- HTTP status + response body
- Whether `commit_created` matches reality
- Whether the audit row is accurate
- Any surprise (slug, path, message, friction)

### 5. Tests

Unit:

- `test_writes_git.py` — add `test_commit_raises_nothing_to_commit_when_must`
  and `test_commit_returns_false_when_optional`. Pin the contract.

Integration:

- Update `test_triage_discard_with_gitignored_queue` to assert
  `commit_created: false` in the response and the audit row.
- Update `test_triage_keep_with_gitignored_queue` to assert
  `commit_created: true`.
- Update `test_edit_frontmatter_commits` to assert `commit_created:
  true`.

### 6. Failure modes & required handling

| Failure                                                  | Action                                                                  |
| -------------------------------------------------------- | ----------------------------------------------------------------------- |
| `triage_keep` for a slug whose target catalog file exists | Already raises `FileExistsError`; current 8.3 router doesn't translate this. Add 409 with `code: "target-exists"`. |
| `triage_merge` against a non-existent target slug         | Raises `FileNotFoundError`; translate to 404 with `code: "target-not-found"`. |
| Parent-child cascade: keep parent, child's path changes  | Child's queue file is unchanged; only parent moves. Out of scope here — just note in dogfood findings. |
| Pre-commit hook blocks the commit                        | Already: GitError propagates; rollback runs. Add a test pinning this on a fixture with a failing hook. |

## Task breakdown

| #  | Task                                                                                          | Notes                                  |
| -- | --------------------------------------------------------------------------------------------- | -------------------------------------- |
| 1  | Add `NothingToCommit` + `must_commit` to `web/apps/api/writes/git.py`.                       | Tuple return changes call sites.       |
| 2  | Update `editor.py`'s three `edit_*` to call `commit(..., must_commit=True)`.                 | Surface `commit_created` in `WriteResult`. |
| 3  | Update `triage.py`'s `triage_keep`/`triage_merge` to `must_commit=True`; `triage_discard` to `must_commit=False`. | Same on `TriageResult`.      |
| 4  | Update `routers/writes.py` to: thread `commit_created` into the wire response; translate `FileExistsError` → 409. | Three edit endpoints + one triage endpoint. |
| 5  | Update Pydantic models + `api-types.ts` mirror.                                              |                                        |
| 6  | Update `audit.commit(result=...)` calls to include `commit_created`.                          |                                        |
| 7  | Unit: `test_writes_git.py` for `NothingToCommit` and the (sha, created) tuple.                |                                        |
| 8  | Update existing integration tests' assertions on `commit_created`.                            |                                        |
| 9  | Run a single quality-gate pass: ruff + pytest + smoke.                                        |                                        |
| 10 | Dogfood: triage 10–15 candidates per § 4. Record surprises.                                  |                                        |
| 11 | Findings doc at `docs/plans/phase-8-3-hardening-findings.md`.                                |                                        |
| 12 | Commit fixes (one commit). Commit findings (separate commit or bundled — operator's call).    |                                        |
| 13 | Update this plan's frontmatter: `status: done`; `completed_at`; finalise `locked_decisions`.  |                                        |

## Quality gate (must all pass before commit)

```sh
uv run ruff check scout/ web/ tests/ tools/
uv run pytest -q
uv run pytest tests/integration/web -q

# Smoke (manual)
rm -rf web/.data
AUTOCLAUDE_API_PORT=8765 uv run autoclaude-api &
# Drive the 10–15 dogfood triages via curl per § 4.
# Verify each response includes `commit_created` and the value matches
# the actual git history.
kill %1
```

## Outcome → next session recommendation

By the end of this sub-phase the operator will have:

- Triaged ~15 candidates by hand via curl across two dogfood passes (5 + 15).
- A felt sense of how much friction the curl-driven path actually is.
- Concrete data on edge cases (parent-child cascade, slug renames,
  famous-person discards).

That informs the next session's fork:

- **If curl-driven triage feels low-friction** (e.g., a script
  wrapper makes it pleasant): go 9.0 reviewer agent next. The
  proposal table is real; we can feed it from an LLM and the
  operator's curl-loop becomes "approve / reject."
- **If curl-driven triage feels bad** (e.g., the slug munging is
  annoying, optimistic-lock 409s on stale fetches): go 8.3b frontend
  next. The UI removes that friction before the reviewer adds load.

This plan does NOT pre-commit to the fork. The dogfood is the input
to that decision.

## Commit message (template)

```
Phase 8.3 hardening: audit honesty (W1+W3) + extended dogfood

- web/apps/api/writes/git.py: NothingToCommit + must_commit flag.
  commit() now returns (sha, commit_created). triage_discard passes
  must_commit=False; everything else defaults to True.
- web/apps/api/writes/{editor,triage}.py: WriteResult and TriageResult
  carry commit_created. Audit row records it.
- Pydantic + TS wire: commit_created on WriteResponse / TriageResponse.
- routers/writes.py: FileExistsError -> 409 (target-exists);
  FileNotFoundError -> 404 (target-not-found).
- tests: NothingToCommit unit + integration assertions on
  commit_created.
- docs/plans/phase-8-3-hardening.md: status -> done.
- docs/plans/phase-8-3-hardening-findings.md: dogfood-2 surprises,
  next-session recommendation.

Catalog grew by N entries (slugs listed in the findings doc).
```

## When this plan becomes stale

`status: active` while the session is in flight. Flips to `done` when
the commit lands and the findings doc has been written. If the
dogfood surfaces something that changes the W1/W3 design, this plan
is amended in-place (it's small enough); larger reshapes spawn a
successor plan that supersedes this one.
