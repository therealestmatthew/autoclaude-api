---
name: tools-readme
title: "Repo-meta tools"
kind: readme
status: active
updated_at: 2026-06-15
---

# /tools/

Repo-wide introspection and housekeeping utilities. Distinct from `/scout/`, which ingests *external* content — anything here operates on the repository itself.

## Modules

- [`manifest.py`](manifest.py) — walks `git ls-files`, parses YAML frontmatter from markdown documents and `<path>.meta.yaml` sidecars from binary documents, emits `MANIFEST.md` at the repo root. CLI exposed as `manifest`. See `conventions/frontmatter.md` for the rules it enforces.

## CLI

```sh
uv run manifest                       # write MANIFEST.md
uv run manifest --stdout              # markdown to stdout
uv run manifest --json                # JSON records to stdout
uv run manifest --check               # exit non-zero if any document has issues
```

`--check` is intended for use in pre-commit hooks or CI once the existing frontmatter backfill is complete. Until then, expect the manifest to list many documents under "with validation issues" — that list **is** the backfill punch list.

## When to add a tool here

When you have a utility that touches the repo itself (catalog linting, link validation, asset re-fingerprinting, etc.). If it operates on external content, it belongs under `/scout/` or a new external-facing subsystem.
