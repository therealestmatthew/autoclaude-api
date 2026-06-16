"""Dedup engine — automated triage and grouping for /scout/queue and /catalog.

Public surface:
  - run_passes(queue_dir, catalog_dir, state_dir, …) -> DedupReport
  - DedupReport dataclass (per-pass counts)

Read /docs/plans/phase-6-merge-dedup.md for design rationale. The engine is
a pure function of disk state + state ledgers; running it twice in a row
produces identical state on the second run (idempotency contract).
"""

from .engine import DedupReport, run_passes

__all__ = ["DedupReport", "run_passes"]
