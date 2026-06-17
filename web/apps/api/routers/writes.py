"""Write-back endpoints — catalog edits + queue triage.

Every write is gated by an optimistic-lock token (`expected_version`),
records to the audit log before the file changes, performs a single
git commit, and finalises the audit row.

The router is thin: it resolves the asset, hands off to the right
write-service function, and translates exceptions to HTTP statuses.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..cache import CachedIndex
from ..db.models import Asset
from ..models import (
    EditBodyRequest,
    EditFrontmatterRequest,
    EditFullRequest,
    TriageRequest,
    TriageResponse,
    WriteResponse,
)
from ..writes import editor, triage
from ..writes.audit import begin_audit
from .deps import get_index

router = APIRouter(tags=["writes"])


def _session(index: CachedIndex) -> Session:
    return index.session_factory()


def _find_record(session: Session, bucket: str, slug: str) -> Asset | None:
    from sqlalchemy import select

    rows = (
        session.execute(
            select(Asset).where(Asset.bucket == bucket, Asset.slug == slug)
        )
        .scalars()
        .all()
    )
    # Slug uniqueness within a bucket: pick first (path-sorted) matching
    # the 8.1 by_slug() first-wins semantics.
    rows.sort(key=lambda r: r.path)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Catalog edits
# ---------------------------------------------------------------------------


@router.put("/catalog/{slug}", response_model=WriteResponse)
def edit_catalog_full(
    slug: str,
    body: EditFullRequest,
    index: CachedIndex = Depends(get_index),
) -> WriteResponse:
    return _edit_full("catalog", slug, body, index)


@router.put("/catalog/{slug}/frontmatter", response_model=WriteResponse)
def edit_catalog_frontmatter(
    slug: str,
    body: EditFrontmatterRequest,
    index: CachedIndex = Depends(get_index),
) -> WriteResponse:
    return _edit_frontmatter("catalog", slug, body, index)


@router.put("/catalog/{slug}/body", response_model=WriteResponse)
def edit_catalog_body(
    slug: str,
    body: EditBodyRequest,
    index: CachedIndex = Depends(get_index),
) -> WriteResponse:
    return _edit_body("catalog", slug, body, index)


# ---------------------------------------------------------------------------
# Queue triage
# ---------------------------------------------------------------------------


@router.post("/queue/{slug}/triage", response_model=TriageResponse)
def triage_queue(
    slug: str,
    body: TriageRequest,
    index: CachedIndex = Depends(get_index),
) -> TriageResponse:
    repo_root: Path = index.repo_root
    session = _session(index)
    try:
        row = _find_record(session, "queue", slug)
        if row is None:
            raise HTTPException(status_code=404, detail=f"queue candidate not found: {slug}")
        intent = body.model_dump()
        with begin_audit(
            session,
            actor="operator",
            action=f"triage-{body.action}",
            target_path=row.path,
            target_bucket="queue",
            intent=intent,
        ) as audit:
            try:
                if body.action == "keep":
                    result = triage.triage_keep(
                        repo_root,
                        row.path,
                        expected_version=body.expected_version,
                        target_slug=body.target_slug,
                        commit_message=body.commit_message,
                    )
                elif body.action == "merge":
                    if not body.target_slug:
                        raise HTTPException(
                            status_code=422,
                            detail="`target_slug` is required for action=merge",
                        )
                    result = triage.triage_merge(
                        repo_root,
                        row.path,
                        target_slug=body.target_slug,
                        expected_version=body.expected_version,
                        commit_message=body.commit_message,
                    )
                else:  # discard
                    if not body.notes:
                        raise HTTPException(
                            status_code=422,
                            detail="`notes` is required for action=discard",
                        )
                    result = triage.triage_discard(
                        repo_root,
                        row.path,
                        expected_version=body.expected_version,
                        notes=body.notes,
                        commit_message=body.commit_message,
                    )
            except editor.VersionMismatch as e:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "version-mismatch",
                        "expected": e.expected_version,
                        "current": e.current_version,
                    },
                ) from e
            except editor.DirtyTree as e:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "dirty-tree", "message": str(e)},
                ) from e
            audit.commit(
                result={
                    "commit_sha": result.commit_sha,
                    "target_path": result.target_path,
                }
            )
        # The route handler ran inside the `with` block; trigger a sync
        # so the next GET reflects the new state.
        index.sync()
        return TriageResponse(
            action=result.action,  # type: ignore[arg-type]
            source_path=result.source_path,
            target_path=result.target_path,
            commit_sha=result.commit_sha,
            new_version=result.new_version,
            audit_id=audit.id,
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _edit_full(
    bucket: str,
    slug: str,
    body: EditFullRequest,
    index: CachedIndex,
) -> WriteResponse:
    repo_root: Path = index.repo_root
    session = _session(index)
    try:
        row = _find_record(session, bucket, slug)
        if row is None:
            raise HTTPException(status_code=404, detail=f"{bucket}/{slug} not found")
        with begin_audit(
            session,
            actor="operator",
            action="edit-full",
            target_path=row.path,
            target_bucket=bucket,
            intent=body.model_dump(),
        ) as audit:
            try:
                result = editor.edit_full(
                    repo_root,
                    row.path,
                    frontmatter=body.frontmatter,
                    body=body.body,
                    expected_version=body.expected_version,
                    commit_message=body.commit_message
                    or f"web: edit {bucket}/{slug}",
                )
            except editor.VersionMismatch as e:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "version-mismatch",
                        "expected": e.expected_version,
                        "current": e.current_version,
                    },
                ) from e
            except editor.DirtyTree as e:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "dirty-tree", "message": str(e)},
                ) from e
            audit.commit(result={"commit_sha": result.commit_sha})
        index.sync()
        return WriteResponse(
            path=result.path,
            commit_sha=result.commit_sha,
            new_version=result.new_version,
            audit_id=audit.id,
        )
    finally:
        session.close()


def _edit_frontmatter(
    bucket: str,
    slug: str,
    body: EditFrontmatterRequest,
    index: CachedIndex,
) -> WriteResponse:
    repo_root: Path = index.repo_root
    session = _session(index)
    try:
        row = _find_record(session, bucket, slug)
        if row is None:
            raise HTTPException(status_code=404, detail=f"{bucket}/{slug} not found")
        with begin_audit(
            session,
            actor="operator",
            action="edit-frontmatter",
            target_path=row.path,
            target_bucket=bucket,
            intent=body.model_dump(),
        ) as audit:
            try:
                result = editor.edit_frontmatter(
                    repo_root,
                    row.path,
                    frontmatter=body.frontmatter,
                    expected_version=body.expected_version,
                    commit_message=body.commit_message
                    or f"web: edit {bucket}/{slug} frontmatter",
                )
            except editor.VersionMismatch as e:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "version-mismatch",
                        "expected": e.expected_version,
                        "current": e.current_version,
                    },
                ) from e
            except editor.DirtyTree as e:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "dirty-tree", "message": str(e)},
                ) from e
            audit.commit(result={"commit_sha": result.commit_sha})
        index.sync()
        return WriteResponse(
            path=result.path,
            commit_sha=result.commit_sha,
            new_version=result.new_version,
            audit_id=audit.id,
        )
    finally:
        session.close()


def _edit_body(
    bucket: str,
    slug: str,
    body: EditBodyRequest,
    index: CachedIndex,
) -> WriteResponse:
    repo_root: Path = index.repo_root
    session = _session(index)
    try:
        row = _find_record(session, bucket, slug)
        if row is None:
            raise HTTPException(status_code=404, detail=f"{bucket}/{slug} not found")
        with begin_audit(
            session,
            actor="operator",
            action="edit-body",
            target_path=row.path,
            target_bucket=bucket,
            intent=body.model_dump(),
        ) as audit:
            try:
                result = editor.edit_body(
                    repo_root,
                    row.path,
                    body=body.body,
                    expected_version=body.expected_version,
                    commit_message=body.commit_message
                    or f"web: edit {bucket}/{slug} body",
                )
            except editor.VersionMismatch as e:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "version-mismatch",
                        "expected": e.expected_version,
                        "current": e.current_version,
                    },
                ) from e
            except editor.DirtyTree as e:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "dirty-tree", "message": str(e)},
                ) from e
            audit.commit(result={"commit_sha": result.commit_sha})
        index.sync()
        return WriteResponse(
            path=result.path,
            commit_sha=result.commit_sha,
            new_version=result.new_version,
            audit_id=audit.id,
        )
    finally:
        session.close()
