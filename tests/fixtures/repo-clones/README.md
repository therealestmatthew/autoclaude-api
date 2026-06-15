---
name: repo-clones-fixtures-readme
title: "Repo-extractor fixture clones"
kind: readme
status: active
updated_at: 2026-06-15
---

# repo-clones/

Synthetic "clone layouts" used by the Phase 4 repo-extractor tests. Each
directory is what the host *would* extract from a real container's tar —
laid out as if `tarfile.extractall()` had already run, with a
`.scout-manifest.json` describing the bytes the container would have
hashed.

The integration test (`tests/integration/test_repo_extract_e2e.py`) walks
one of these directories, packs it into a tar in-memory, and feeds the
bytes to `RepoExtractor` with the container call stubbed out. That keeps
tests fast (no docker, no network) while exercising the host-side
extraction + detection + slugging.

## Fixtures

- `minimal-with-agent/` — `.claude/agents/code-reviewer.md` only.
- `minimal-with-skill/` — `skills/test-runner/SKILL.md` only.
- `mcp-server-config/` — `.claude/mcp.json` with two `mcpServers` entries.
- `with-prompts/` — `prompts/triage.md` with `kind: prompt` frontmatter.
- `hostile-symlink/` — contains an entry that the tar packer turns into a
  symlink; the extractor must reject the whole tar.
- `oversize/` — contains a file larger than the 1 MB per-file cap; the
  extractor must skip just that file.

## Why fixtures and not pytest tmp_path

Two reasons:

1. Reading a layout off disk makes the intent of each fixture obvious in
   one place (`ls -R`), instead of reconstructing it inline in every test.
2. The detection rules care about real file layouts. Building them
   inline in Python makes the test code more about the scaffolding than
   the assertion.
