"""Pydantic API models — the wire format.

Kept separate from the `AssetRecord` dataclass in `indexer.py` so the
internal representation can evolve without breaking the API contract.
Conversion happens in `routers/_serialize.py`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Re-exported so router types match the indexer's vocabulary.
Bucket = Literal[
    "catalog",
    "queue",
    "engagement",
    "convention",
    "plan",
    "session_prompt",
    "runbook",
    "readme",
    "claude",
    "consulting",
    "other",
]


class Health(BaseModel):
    ok: bool = True
    version: str
    repo_root: str
    records: int = Field(description="Number of indexed records.")


class AssetSummary(BaseModel):
    """The list-shape — small, fast to serialize, no body."""

    path: str
    bucket: Bucket
    slug: str
    kind: str | None = None
    title: str | None = None
    status: str | None = None
    quality: int | None = None
    tags: list[str] = []
    created_at: str | None = None
    updated_at: str | None = None
    issues: list[str] = []


class AssetDetail(AssetSummary):
    """The detail-shape — adds body and structured frontmatter blobs."""

    body: str
    source: dict | None = None
    discovered: dict | None = None
    relations: dict | None = None


class Stats(BaseModel):
    total: int
    by_bucket: dict[str, int]
    by_kind: dict[str, int]
    by_status: dict[str, int]
    with_issues: int


class StatsResponse(BaseModel):
    stats: Stats
    repo_root: str
    snapshot_mtime: float


class ListResponse(BaseModel):
    items: list[AssetSummary]
    total: int


class SearchHit(AssetSummary):
    score: float
    matched: list[str] = Field(
        default_factory=list,
        description="Which fields matched the query (title, slug, tags, body).",
    )


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
    total: int


class ThreadEvent(BaseModel):
    date: str
    thread_id: str | None = None
    agent: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    outcome: str | None = None
    summary: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw: dict


class ThreadResponse(BaseModel):
    events: list[ThreadEvent]
    total: int
    days_scanned: int


class SyncResponse(BaseModel):
    stats: Stats
    rebuilt: bool = True
