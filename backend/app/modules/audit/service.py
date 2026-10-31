"""Append-only, hash-chained audit trail (tamper-evident) persisted in the database."""
from __future__ import annotations

import hashlib
import threading
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.core.clock import Clock
from app.core.redaction import redact
from app.database.models import AuditEventRow
from app.database.session import Database
from app.modules.policy.hashing import canonical_json

GENESIS = "0" * 64


class AuditEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    seq: int
    ts: Any
    session_id: str | None
    merchant_id: str | None
    event_type: str
    actor: str
    tool_name: str | None
    decision: str | None
    tier: int | None
    risk_score: int | None
    payload: dict[str, Any]
    hash: str


class ChainVerification(BaseModel):
    valid: bool
    events_checked: int
    first_invalid_seq: int | None = None


def _digest(prev_hash: str, row: AuditEventRow) -> str:
    body = {
        "ts": row.ts.isoformat(), "session_id": row.session_id, "merchant_id": row.merchant_id,
        "event_type": row.event_type, "actor": row.actor, "tool_name": row.tool_name,
        "decision": row.decision, "tier": row.tier, "risk_score": row.risk_score,
        "payload": row.payload,
    }
    return hashlib.sha256((prev_hash + canonical_json(body)).encode()).hexdigest()


class AuditService:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        # Serialises chain appends within one process. Multi-instance deployments need a DB-level
        # lock (e.g. pg_advisory_xact_lock) or a single writer to keep the chain strictly ordered.
        self._lock = threading.Lock()

    def record(
        self,
        event_type: str,
        actor: str,
        *,
        session_id: str | None = None,
        merchant_id: str | None = None,
        tool_name: str | None = None,
        decision: str | None = None,
        tier: int | None = None,
        risk_score: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        with self._lock, self._db.session() as s:
            prev = s.scalar(select(AuditEventRow.hash).order_by(AuditEventRow.seq.desc()).limit(1))
            row = AuditEventRow(
                ts=self._clock.now(), session_id=session_id, merchant_id=merchant_id,
                event_type=event_type, actor=actor, tool_name=tool_name, decision=decision,
                tier=tier, risk_score=risk_score, payload=redact(payload or {}),
                prev_hash=prev or GENESIS, hash="",
            )
            row.hash = _digest(row.prev_hash, row)
            s.add(row)
            s.flush()
            return row.seq

    def count(self, session_id: str, event_type: str) -> int:
        with self._db.session() as s:
            return s.scalar(
                select(func.count()).select_from(AuditEventRow).where(
                    AuditEventRow.session_id == session_id, AuditEventRow.event_type == event_type
                )
            ) or 0

    def list_events(self, session_id: str | None = None, limit: int = 100) -> list[AuditEvent]:
        stmt = select(AuditEventRow).order_by(AuditEventRow.seq.desc()).limit(min(limit, 500))
        if session_id:
            stmt = stmt.where(AuditEventRow.session_id == session_id)
        with self._db.session() as s:
            rows = list(s.scalars(stmt))
        return [AuditEvent.model_validate(r) for r in reversed(rows)]

    def verify_chain(self) -> ChainVerification:
        prev, n = GENESIS, 0
        with self._db.session() as s:
            for row in s.scalars(select(AuditEventRow).order_by(AuditEventRow.seq)):
                n += 1
                if row.prev_hash != prev or row.hash != _digest(prev, row):
                    return ChainVerification(valid=False, events_checked=n, first_invalid_seq=row.seq)
                prev = row.hash
        return ChainVerification(valid=True, events_checked=n)
