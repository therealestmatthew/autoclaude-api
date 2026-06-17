"""Dashboard / health endpoints — aggregates over the snapshot."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..cache import CachedIndex
from ..models import Health, Stats, StatsResponse, SyncResponse
from .deps import get_index

router = APIRouter(tags=["meta"])

# Bumped on every observable change to the API surface (routes, response shapes).
API_VERSION = "0.1.0"


def _stats_from(snapshot) -> Stats:
    s = snapshot.stats()
    return Stats(
        total=s.total,
        by_bucket={k: v for k, v in s.by_bucket.items()},
        by_kind=s.by_kind,
        by_status=s.by_status,
        with_issues=s.with_issues,
    )


@router.get("/health", response_model=Health)
def health(index: CachedIndex = Depends(get_index)) -> Health:
    snapshot = index.get()
    return Health(
        ok=True,
        version=API_VERSION,
        repo_root=snapshot.repo_root,
        records=len(snapshot.records),
    )


@router.get("/stats", response_model=StatsResponse)
def stats(index: CachedIndex = Depends(get_index)) -> StatsResponse:
    snapshot = index.get()
    return StatsResponse(
        stats=_stats_from(snapshot),
        repo_root=snapshot.repo_root,
        snapshot_mtime=snapshot.scan_mtime_ceiling,
    )


@router.post("/sync", response_model=SyncResponse)
def sync(index: CachedIndex = Depends(get_index)) -> SyncResponse:
    snapshot = index.force_rebuild()
    return SyncResponse(stats=_stats_from(snapshot), rebuilt=True)
