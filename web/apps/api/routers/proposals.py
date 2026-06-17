"""Proposal CRUD + accept / reject.

Proposals are the wire that connects the 9.0 reviewer agent to the
8.3 operator UI. v1 ships:

- GET    /proposals             — filter + list
- GET    /proposals/{id}        — detail
- POST   /proposals             — operator drafts (rare in v1)
- POST   /proposals/{id}/accept — translate to triage call + finalise
- POST   /proposals/{id}/reject — drop the proposal; audit the reason
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from ..cache import CachedIndex
from ..db.models import Proposal
from ..models import (
    AcceptProposalRequest,
    CreateProposalRequest,
    ProposalDetail,
    ProposalListResponse,
    ProposalSummary,
    RejectProposalRequest,
    TriageRequest,
    TriageResponse,
)
from ..writes.audit import begin_audit
from .deps import get_index
from .writes import triage_queue

router = APIRouter(prefix="/proposals", tags=["proposals"])


def _summary(p: Proposal) -> ProposalSummary:
    return ProposalSummary(
        id=p.id,
        created_at=p.created_at,
        source=p.source,
        target_path=p.target_path,
        target_bucket=p.target_bucket,
        action_kind=p.action_kind,
        summary=p.summary,
        confidence=p.confidence,
        status=p.status,
    )


def _detail(p: Proposal) -> ProposalDetail:
    return ProposalDetail(
        **_summary(p).model_dump(),
        payload=p.payload,
        rationale=p.rationale,
        decided_at=p.decided_at,
        decided_by=p.decided_by,
        decision_audit_id=p.decision_audit_id,
    )


@router.get("", response_model=ProposalListResponse)
def list_proposals(
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    target_bucket: str | None = Query(default=None),
    target_path: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    index: CachedIndex = Depends(get_index),
) -> ProposalListResponse:
    session = index.session_factory()
    try:
        stmt = select(Proposal)
        if status:
            stmt = stmt.where(Proposal.status == status)
        if source:
            stmt = stmt.where(Proposal.source == source)
        if target_bucket:
            stmt = stmt.where(Proposal.target_bucket == target_bucket)
        if target_path:
            stmt = stmt.where(Proposal.target_path == target_path)
        rows = session.execute(stmt).scalars().all()
        rows.sort(key=lambda r: (-r.created_at, r.id))
        total = len(rows)
        page = rows[offset : offset + limit]
        return ProposalListResponse(
            items=[_summary(p) for p in page],
            total=total,
        )
    finally:
        session.close()


@router.get("/{proposal_id}", response_model=ProposalDetail)
def get_proposal(
    proposal_id: str, index: CachedIndex = Depends(get_index)
) -> ProposalDetail:
    session = index.session_factory()
    try:
        row = session.get(Proposal, proposal_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"proposal not found: {proposal_id}")
        return _detail(row)
    finally:
        session.close()


@router.post("", response_model=ProposalDetail, status_code=201)
def create_proposal(
    body: CreateProposalRequest, index: CachedIndex = Depends(get_index)
) -> ProposalDetail:
    session = index.session_factory()
    try:
        new = Proposal(
            id=uuid.uuid4().hex,
            created_at=time.time(),
            source=body.source,
            target_path=body.target_path,
            target_bucket=body.target_bucket,
            action_kind=body.action_kind,
            payload=body.payload,
            summary=body.summary,
            rationale=body.rationale,
            confidence=body.confidence,
            status="pending",
        )
        session.add(new)
        session.commit()
        return _detail(new)
    finally:
        session.close()


@router.post("/{proposal_id}/accept", response_model=TriageResponse)
def accept_proposal(
    proposal_id: str,
    body: AcceptProposalRequest,
    index: CachedIndex = Depends(get_index),
) -> TriageResponse:
    session = index.session_factory()
    try:
        proposal = session.get(Proposal, proposal_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail=f"proposal not found: {proposal_id}")
        if proposal.status != "pending":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "not-pending",
                    "current_status": proposal.status,
                },
            )
        if proposal.target_bucket != "queue":
            raise HTTPException(
                status_code=422,
                detail="only queue-targeted proposals can be accepted via this endpoint in v1",
            )

        # Pull the queue row to find the slug + current version.
        from ..db.models import Asset

        rows = (
            session.execute(
                select(Asset).where(Asset.path == proposal.target_path)
            )
            .scalars()
            .all()
        )
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"proposal target no longer exists: {proposal.target_path}",
            )
        asset = rows[0]
        expected_version = body.expected_version or asset.version

        # Build the triage request from the proposal's payload + action.
        triage_req = TriageRequest(
            action=proposal.action_kind,  # type: ignore[arg-type]
            expected_version=expected_version,
            target_slug=proposal.payload.get("target_slug")
            or proposal.payload.get("suggested_slug"),
            notes=proposal.payload.get("notes") or proposal.rationale,
            commit_message=f"web: accept proposal {proposal.id[:8]} ({proposal.action_kind})",
        )
        result = triage_queue(slug=asset.slug, body=triage_req, index=index)

        # Mark the proposal accepted; link to the triage's audit row.
        proposal.status = "accepted"
        proposal.decided_at = time.time()
        proposal.decided_by = "operator"
        proposal.decision_audit_id = result.audit_id
        session.commit()
        return result
    finally:
        session.close()


@router.post("/{proposal_id}/reject", response_model=ProposalDetail)
def reject_proposal(
    proposal_id: str,
    body: RejectProposalRequest,
    index: CachedIndex = Depends(get_index),
) -> ProposalDetail:
    if not body.notes.strip():
        raise HTTPException(
            status_code=422, detail="`notes` is required when rejecting a proposal"
        )
    session = index.session_factory()
    try:
        proposal = session.get(Proposal, proposal_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail=f"proposal not found: {proposal_id}")
        if proposal.status != "pending":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "not-pending",
                    "current_status": proposal.status,
                },
            )
        # The rejection itself goes through the audit log so the
        # decision history is queryable like any other write.
        with begin_audit(
            session,
            actor="operator",
            action="reject-proposal",
            target_path=proposal.target_path,
            target_bucket=proposal.target_bucket,
            intent={"proposal_id": proposal.id, "notes": body.notes},
        ) as audit:
            proposal.status = "rejected"
            proposal.decided_at = time.time()
            proposal.decided_by = "operator"
            proposal.decision_audit_id = audit.id
            audit.commit(result={"proposal_id": proposal.id}, notes=body.notes)
        session.commit()
        return _detail(proposal)
    finally:
        session.close()
