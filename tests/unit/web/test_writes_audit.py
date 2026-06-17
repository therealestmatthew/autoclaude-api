"""Tests for the audit-row context manager."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from web.apps.api.db.models import AuditEvent
from web.apps.api.writes.audit import begin_audit, sweep_orphan_pending


def _audit_kwargs() -> dict:
    return dict(
        actor="operator",
        action="edit-frontmatter",
        target_path="catalog/x.md",
        target_bucket="catalog",
        intent={"foo": "bar"},
    )


def test_audit_commits_on_clean_exit(db_factory: sessionmaker[Session]) -> None:
    session = db_factory()
    with begin_audit(session, **_audit_kwargs()) as audit:
        audit.commit(result={"sha": "abc123"})
    row = db_factory().get(AuditEvent, audit.id)
    assert row is not None
    assert row.status == "committed"
    assert row.result == {"sha": "abc123"}


def test_audit_fails_on_exception(db_factory: sessionmaker[Session]) -> None:
    session = db_factory()
    with (
        pytest.raises(RuntimeError, match="planned"),
        begin_audit(session, **_audit_kwargs()) as audit,
    ):
        raise RuntimeError("planned")
    row = db_factory().get(AuditEvent, audit.id)
    assert row.status == "failed"
    assert "planned" in row.result["error_message"]


def test_audit_without_commit_call_is_failed(
    db_factory: sessionmaker[Session],
) -> None:
    session = db_factory()
    with begin_audit(session, **_audit_kwargs()) as audit:
        pass  # forget to call audit.commit()
    row = db_factory().get(AuditEvent, audit.id)
    assert row.status == "failed"
    assert "exited without calling audit.commit" in row.result["error_message"]


def test_pending_row_visible_during_work(
    db_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    """A pending row is visible to other sessions while the writer runs.
    Critical for the crash-recovery story."""
    session = db_factory()
    with begin_audit(session, **_audit_kwargs()) as audit:
        with db_factory() as observer:
            row = observer.get(AuditEvent, audit.id)
        assert row is not None
        assert row.status == "pending"
        audit.commit(result={"sha": "x"})


def test_sweep_finalises_old_pending(db_factory: sessionmaker[Session]) -> None:
    session = db_factory()
    # Manually insert a stale pending row.
    stale = AuditEvent(
        id="aaaa-stale",
        created_at=time.time() - 3600,
        updated_at=time.time() - 3600,
        actor="operator",
        action="edit-frontmatter",
        target_path="catalog/x.md",
        target_bucket="catalog",
        status="pending",
        intent={},
    )
    session.add(stale)
    session.commit()
    moved = sweep_orphan_pending(db_factory(), older_than_seconds=60)
    assert moved == 1
    row = db_factory().get(AuditEvent, "aaaa-stale")
    assert row.status == "failed"
    assert "orphan pending" in row.result["error_message"]


def test_sweep_ignores_recent_pending(db_factory: sessionmaker[Session]) -> None:
    session = db_factory()
    fresh = AuditEvent(
        id="bbbb-fresh",
        created_at=time.time() - 1,
        updated_at=time.time() - 1,
        actor="operator",
        action="edit-frontmatter",
        target_path="catalog/x.md",
        target_bucket="catalog",
        status="pending",
        intent={},
    )
    session.add(fresh)
    session.commit()
    moved = sweep_orphan_pending(db_factory(), older_than_seconds=60)
    assert moved == 0
    row = db_factory().get(AuditEvent, "bbbb-fresh")
    assert row.status == "pending"
