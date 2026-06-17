"""Pending → committed/failed audit transitions.

The contract:

- `with begin_audit(...) as audit:` opens a pending row.
- On clean exit, `audit.commit(result=...)` transitions to committed.
- On exception, the manager finalises as failed with the traceback.
- A pending row that survives a process restart is a crash signal —
  the sweeper picks it up and marks it failed.

This is the load-bearing piece of 8.3's atomicity story: even if a
file write succeeds and the git commit dies, the audit row records the
intent and the failure so the operator can recover.
"""

from __future__ import annotations

import time
import traceback
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from ..db.models import AuditEvent


@dataclass
class AuditHandle:
    id: str
    actor: str
    action: str
    target_path: str
    target_bucket: str
    intent: dict[str, Any]
    session: Session
    _committed: bool = field(default=False, init=False)
    _result: dict[str, Any] | None = field(default=None, init=False)
    _notes: str | None = field(default=None, init=False)

    def commit(self, *, result: dict[str, Any] | None = None, notes: str | None = None) -> None:
        """Mark the row as committed. Must be called inside `begin_audit`."""
        self._committed = True
        self._result = result
        self._notes = notes


@contextmanager
def begin_audit(
    session: Session,
    *,
    actor: str,
    action: str,
    target_path: str,
    target_bucket: str,
    intent: dict[str, Any],
) -> Iterator[AuditHandle]:
    """Open a pending audit row, yield a handle, then finalise.

    Commits in three transactions:
    1. Insert the pending row (so a crash is observable).
    2. Yield to the caller (which does the file + git work).
    3. Finalise to committed or failed.

    The caller's `session` is used. The caller must NOT begin or commit
    a transaction inside the `with` block — finalisation owns the
    session at finalise time.
    """
    audit_id = uuid.uuid4().hex
    now = time.time()
    row = AuditEvent(
        id=audit_id,
        created_at=now,
        updated_at=now,
        actor=actor,
        action=action,
        target_path=target_path,
        target_bucket=target_bucket,
        status="pending",
        intent=intent,
        result=None,
        notes=None,
    )
    session.add(row)
    session.commit()

    handle = AuditHandle(
        id=audit_id,
        actor=actor,
        action=action,
        target_path=target_path,
        target_bucket=target_bucket,
        intent=intent,
        session=session,
    )

    try:
        yield handle
    except Exception as e:  # noqa: BLE001 — we want everything
        row = session.get(AuditEvent, audit_id)
        if row is not None:
            row.status = "failed"
            row.updated_at = time.time()
            row.result = {
                "error_class": e.__class__.__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc(),
            }
        session.commit()
        raise
    else:
        row = session.get(AuditEvent, audit_id)
        if row is not None:
            row.status = "committed" if handle._committed else "failed"
            row.updated_at = time.time()
            row.result = handle._result
            row.notes = handle._notes
            if not handle._committed:
                row.result = (row.result or {}) | {
                    "error_message": "writer exited without calling audit.commit()"
                }
        session.commit()


def sweep_orphan_pending(session: Session, *, older_than_seconds: float = 120.0) -> int:
    """Mark every pending audit row older than the threshold as failed.

    Called from the index sync tail. The default threshold (2× the
    reconcile interval) gives in-flight writes a comfortable window.
    Returns the number of rows transitioned.
    """
    cutoff = time.time() - older_than_seconds
    rows = (
        session.query(AuditEvent)
        .filter(AuditEvent.status == "pending", AuditEvent.created_at < cutoff)
        .all()
    )
    for row in rows:
        row.status = "failed"
        row.updated_at = time.time()
        row.result = (row.result or {}) | {
            "error_message": "orphan pending; finalised by sweep",
        }
    if rows:
        session.commit()
    return len(rows)
