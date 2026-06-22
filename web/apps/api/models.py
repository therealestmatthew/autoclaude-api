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
    "brand",
    "timeline",
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
    delivery_functions: list[str] = []
    created_at: str | None = None
    updated_at: str | None = None
    issues: list[str] = []
    # 8.3: optimistic-lock token for write-back. UI passes this back as
    # `expected_version` on any PUT/POST. Empty string means the indexer
    # hasn't seen the row yet (pre-sync); writes should refetch first.
    version: str = ""


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


# ---------------------------------------------------------------------------
# Phase 8.3 — write-back wire shapes
# ---------------------------------------------------------------------------


class EditFrontmatterRequest(BaseModel):
    frontmatter: dict
    expected_version: str = Field(
        description="Optimistic-lock token. Get from the asset detail response."
    )
    commit_message: str | None = None


class EditBodyRequest(BaseModel):
    body: str
    expected_version: str
    commit_message: str | None = None


class EditFullRequest(BaseModel):
    frontmatter: dict
    body: str
    expected_version: str
    commit_message: str | None = None


class WriteResponse(BaseModel):
    path: str
    commit_sha: str
    new_version: str
    audit_id: str
    commit_created: bool = True


class TriageRequest(BaseModel):
    action: Literal["keep", "merge", "discard"]
    expected_version: str
    target_slug: str | None = Field(
        default=None,
        description="Required for `merge`; optional `keep` rename target.",
    )
    notes: str | None = Field(
        default=None,
        description="Required for `discard`; optional otherwise.",
    )
    commit_message: str | None = None


class TriageResponse(BaseModel):
    action: Literal["keep", "merge", "discard"]
    source_path: str
    target_path: str | None
    commit_sha: str
    new_version: str | None
    audit_id: str
    commit_created: bool = True
    cascade: list[dict[str, str]] = Field(default_factory=list)
    # Each element is {"slug": str, "new_parent": str} for rewritten children.


# Proposals are 9.0's payload but the table lives behind 8.3.


class ProposalSummary(BaseModel):
    id: str
    created_at: float
    source: str
    target_path: str
    target_bucket: str
    action_kind: str
    summary: str
    confidence: float | None = None
    status: str


class ProposalDetail(ProposalSummary):
    payload: dict
    rationale: str
    decided_at: float | None = None
    decided_by: str | None = None
    decision_audit_id: str | None = None


class ProposalListResponse(BaseModel):
    items: list[ProposalSummary]
    total: int


class CreateProposalRequest(BaseModel):
    source: Literal["operator", "reviewer-agent"] = "operator"
    target_path: str
    target_bucket: str
    action_kind: Literal["keep", "merge", "discard", "edit"]
    payload: dict
    summary: str
    rationale: str
    confidence: float | None = None


class RejectProposalRequest(BaseModel):
    notes: str


class AcceptProposalRequest(BaseModel):
    # The accept endpoint pulls the if_match from the *target asset's*
    # current version — accepting an old proposal against a moved target
    # should 409. The optional override is for tests.
    expected_version: str | None = None


class AuditEventSummary(BaseModel):
    id: str
    created_at: float
    updated_at: float
    actor: str
    action: str
    target_path: str
    target_bucket: str
    status: str


class AuditEventDetail(AuditEventSummary):
    intent: dict
    result: dict | None = None
    notes: str | None = None


class AuditListResponse(BaseModel):
    items: list[AuditEventSummary]
    total: int


# ---------------------------------------------------------------------------
# Phase 10.1 — Client + Brand + BusinessProcess wire shapes
# ---------------------------------------------------------------------------


class ClientCreate(BaseModel):
    slug: str
    name: str
    industry: str | None = None
    brand_slug: str | None = None
    engagement_context: str | None = None


class ClientUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    brand_slug: str | None = None
    engagement_context: str | None = None


class ClientItem(BaseModel):
    slug: str
    name: str
    industry: str | None = None
    brand_slug: str | None = None
    engagement_context: str | None = None
    created_at: float
    updated_at: float


class ClientListResponse(BaseModel):
    items: list[ClientItem]
    total: int


class BusinessProcessItem(BaseModel):
    slug: str
    name: str
    parent_slug: str | None = None
    description: str | None = None


class BusinessProcessListResponse(BaseModel):
    items: list[BusinessProcessItem]
    total: int


# ---------------------------------------------------------------------------
# Timeline wire shapes — markdown-backed, entries in frontmatter
# ---------------------------------------------------------------------------


class TimelineEntry(BaseModel):
    title: str
    type: str = "event"            # milestone | phase | deliverable | event
    date: str | None = None        # YYYY-MM-DD; required unless start/end set
    start: str | None = None       # YYYY-MM-DD for ranges
    end: str | None = None
    color: str | None = None       # emerald | blue | amber | rose | violet | zinc
    ref: str | None = None         # optional slug to link to (any catalog asset)
    notes: str | None = None


class TimelineSummary(BaseModel):
    path: str
    slug: str
    title: str | None
    status: str | None
    view: str = "list"             # list | month — hint for the renderer
    entry_count: int
    first_date: str | None = None
    last_date: str | None = None
    tags: list[str] = []


class TimelineDetail(TimelineSummary):
    body: str
    entries: list[TimelineEntry]


class TimelineListResponse(BaseModel):
    items: list[TimelineSummary]
    total: int
