# Session prompt — finish Phase 3 (HN / Lobsters / Reddit + security baseline)

Paste the block below as your opening message to a fresh Claude Code session
in `/code/autoclaude`. The plan it points at is comprehensive; this prompt
just primes the session.

---

```
We are resuming Phase 3 of the autoclaude repo. The full plan is at:

  /home/mimmik/.claude/plans/serene-prancing-raven.md

Please read that plan IN FULL before doing anything else, then read these
in order (all small):

  1. CLAUDE.md  (operating brief for the repo)
  2. conventions/security.md  (rules every extractor must follow)
  3. conventions/testing.md  (test directory + protocol)
  4. scout/_security.py  (the toolkit the rules require)
  5. scout/agent/runner.py  (the orchestrator you'll register into)

Then check working-tree state with `git status --short`. You should see
several uncommitted files from a prior session: scout/_security.py,
conventions/security.md, plus partial Phase 3 extractors. The plan's "State
of the working tree" section enumerates them; do NOT delete or stash any of
them — they are the starting point.

Locked decisions (do NOT relitigate):
- Reviewer trust model: human-only, forever.
- Phase 4 sandboxing: container per clone (Docker / podman).
- Retrofit Phase 2 + in-progress Phase 3 to use _security helpers; Reddit is
  written fresh on the baseline.
- sanitize_text length cap: silent truncate.
- SSRF defense: literal-IP only; document DNS-resolution work for later.

Execute the plan's 16 numbered tasks in order. The plan's "Suggested
execution order for delegation" section maps the tasks to chunks suitable
for parallel subagents (general-purpose for code, Explore for any lookups).
Use TaskCreate to track progress.

Quality gate before commit (must all pass):

  uv run ruff check scout/ tests/
  uv run pytest -q
  uv run pytest tests/integration -q

Smoke test each new source live (cleanups + smoke calls in the plan).

Commit everything as ONE logical change using the commit message template in
the plan's task 16. Do not split into multiple commits.

Out of scope for this session: Phase 4 (repo extractor), DNS-resolution SSRF
defense, agent-driven queue review, X / Twitter ingestion, catalog promotion
from /scout/queue/ to /catalog/.

When done, summarize: tests passing count, ruff status, smoke-test results
per source, commit SHA, and any rough edges that surfaced (especially around
Reddit's User-Agent / rate limits, which may force a switch to
old.reddit.com per the plan).
```

---

## Why this prompt is shaped this way

- **Plan-first.** The body of the plan is large; the prompt cannot inline
  it without becoming the plan itself. Pointing at it keeps the prompt
  short and the plan canonical.
- **Files-second.** The next thing the fresh session needs is the actual
  code it will modify and the conventions it must honor. Five small reads
  is the right cold-start.
- **Locked decisions inlined.** These are the easiest things to forget or
  re-argue without context. Inlining them prevents the fresh session from
  asking questions you've already answered.
- **Out-of-scope inlined.** Prevents scope creep.
- **Final-summary ask.** Forces the session to verify before declaring
  done.

## When this file becomes stale

Delete or archive once Phase 3 commits cleanly. The next session prompt
(Phase 4 — repo extractor) belongs in a new file in this directory.
