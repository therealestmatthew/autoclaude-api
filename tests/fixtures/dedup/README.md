---
name: dedup-fixtures-readme
title: "Dedup engine fixtures"
kind: readme
status: active
updated_at: 2026-06-15
---

# Dedup engine fixtures

Static layouts used by `tests/integration/test_run_once_with_dedup.py` and by
unit tests that want a realistic queue/catalog shape rather than a synthesized
one. Each subdirectory exercises one pass of the engine:

| Subdir                  | Pass | Scenario                                           |
| ----------------------- | ---- | -------------------------------------------------- |
| `exact-duplicate-pair/` | 1    | Two queue candidates with identical `source.url`.  |
| `near-duplicate-pair/`  | 3    | Two queue candidates with high title overlap.      |
| `superseded-chain/`     | 4    | Catalog asset with `relations.supersedes` and old `updated_at` — must auto-archive. |
| `404-streak/`           | 4    | Catalog asset whose URL has 404'd ≥3 times in the liveness state (sidecar JSON). |

Copy these into a `tmp_path` world in tests; do not write tests that mutate
the fixture files in place.
