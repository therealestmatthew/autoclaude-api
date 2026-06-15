---
name: phase-4-repo-extractor-prompt
title: "Session prompt — Phase 4 (repo extractor + container sandbox)"
kind: session-prompt
phase: 4
status: done
related: [phase-4-repo-extractor]
created_at: 2026-06-15
updated_at: 2026-06-15
completed_at: 2026-06-15
---

# Session prompt — Phase 4 (repo extractor + per-clone container sandbox)

Paste the block below as your opening message to a fresh Claude Code session in `/code/autoclaude`. The substantive plan is canonical in-repo at `/docs/plans/phase-4-repo-extractor.md`; this prompt just sequences the cold-start reads.

---

```
We are starting Phase 4 of the autoclaude repo. The full plan is in-repo at:

  /code/autoclaude/docs/plans/phase-4-repo-extractor.md

Read that plan IN FULL before doing anything else, then read these in order
(all small):

  1. CLAUDE.md                            (operating brief; note "Planning lineage")
  2. conventions/security.md              (rules every extractor must follow;
                                           container & static-parsing rules apply)
  3. conventions/naming.md                (slug rules; you will add a child-slug
                                           convention here)
  4. conventions/testing.md               (test directory + protocol)
  5. scout/_security.py                   (sanitize_text, safe_external_url,
                                           safe_get_bytes — still in use)
  6. scout/agent/runner.py                (orchestrator you will register into)
  7. scout/agent/types.py                 (Candidate / SourceState models)
  8. scout/extractors/base.py             (Extractor Protocol)
  9. scout/extractors/awesome_list.py     (reference implementation)
  10. catalog/_schema/asset.schema.md     (target shape of every emitted Candidate)

Then check working-tree state with `git status --short`. The tree should be
clean at the start of Phase 4 — confirm before beginning, and ask if it isn't.

Locked decisions (carried from Phase 3 and set in the plan — do NOT
relitigate):

- Sandbox: per-clone container. Docker is the v1 default; podman support is a
  flag stub raising NotImplementedError.
- Reviewer trust model: human-only, forever. Children land in /scout/queue/,
  never directly in /catalog/.
- Static parsing only inside the container. No pip install, no test runs, no
  python -m of repo contents.
- Repo extraction is queue-triggered (and manually triggerable via CLI), not
  poll-triggered. There is no `repo` source type in /scout/sources/.
- Child slug convention: <repo-slug>--<child-name>. Double-dash. Add to
  conventions/naming.md as part of this phase.
- Per-clone hard caps: 1 MB per file, 100 MB total, 5000 files. Cap exceeded
  → emit partial with a warning in the thread record; never silent truncate.
- Symlink escape (container or host extraction) → reject the entire repo and
  log a security event. No partial success on a hostile repo.
- Host-side re-validation of every path after extracting the container's tar.
  Defense in depth — never trust container output blindly.

Open questions called out in the plan, to be resolved in this session and
moved into `locked_decisions:` in the plan's frontmatter at close:

1. Default container runtime (recommend Docker only in v1; podman stub).
2. Image distribution (recommend local build only; no registry).
3. Temp dir location (recommend tempfile.TemporaryDirectory()).
4. mcp.json parsing — one Candidate per server entry or per file
   (recommend per server).
5. Whether to extract children of plugin repos (recommend no in this phase).

Execute the plan's numbered tasks (1–15) in order; tasks 1–3 and 9–11 are
parallelizable. Use TaskCreate to track progress.

Quality gate before commit (must all pass):

  uv run ruff check scout/ tests/
  uv run pytest -q
  uv run pytest tests/integration -q

Plus the manual smoke test in the plan's "Quality gate" section.

Commit as ONE logical change using the commit message template in the plan's
task 15. Do not split.

Out of scope for this session (do not start):
- Phase 5 (X / Twitter ingestion).
- Phase 6 (automated merge/dedup).
- DNS-resolution SSRF defense (still a tracked follow-up from Phase 3).
- Auto-promotion of children to /catalog/.
- Discovery of repos directly from GitHub (still socials + awesome-lists).

When done, summarize: tests passing count, ruff status, smoke-test results
(queue entries written, any rejected files), the resolution of each of the
five open questions above, the commit SHA, and any rough edges that
surfaced. Then flip the plan's frontmatter to `status: done`, set
`completed_at`, finalise `locked_decisions:`, and rename this prompt file to
`phase-4-repo-extractor.done.md`.
```

---

## Why this prompt is shaped this way

- **Plan-first, in-repo.** Phase 3's prompt pointed at a plan outside the repo (`~/.claude/plans/...`); this prompt points at `/docs/plans/phase-4-repo-extractor.md`, per CLAUDE.md § "Planning lineage." Future sessions and collaborators can see the plan; the design lineage stays with the code.
- **Files-second.** Ten small reads is the right cold-start: the brief, the conventions that bind this phase, the existing scout code the extractor will register into, and the asset schema that defines the output shape.
- **Locked decisions inlined.** Easiest things to forget or re-argue without context. The plan's frontmatter is the authoritative copy; the prompt mirrors them for the session that has not read the plan yet.
- **Open questions inlined with recommendations.** Forces the session to make explicit answers (and move them into the plan's `locked_decisions:` at close) instead of leaving design drift behind.
- **Out-of-scope inlined.** Prevents scope creep, especially around the related-but-deferred items (DNS SSRF, auto-promotion, Phase 5/6 work).
- **Final-summary ask, plus the lineage update.** The session is responsible for flipping plan status and archiving this prompt — that is how Phase 5's prompt can be written without re-deriving Phase 4's outcomes.

## When this file becomes stale

Rename to `phase-4-repo-extractor.done.md` once Phase 4 commits cleanly (per the closing task in the plan). The next session prompt (Phase 5 — X / Twitter ingestion) belongs in a new file in this directory and points at its own in-repo plan at `/docs/plans/phase-5-x-twitter.md`.
