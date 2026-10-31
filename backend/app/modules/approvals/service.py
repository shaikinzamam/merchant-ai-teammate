"""Human-in-the-loop task store: Tier-2 approvals and Tier-3 escalations.

Approvals are bound to an exact action hash, expire, and are single-use (atomic consume).
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update

from app.core.clock import Clock
from app.core.errors import Conflict, Forbidden, NotFound
from app.database.models import HumanTaskRow
from app.database.session import Database
from app.modules.audit.service import AuditService
from app.schemas.domain import (
    ActionContext,
    HumanTask,
    PolicyDecision,
    ProposedAction,
    TaskKind,
    TaskStatus,
)


class HumanTaskService:
    def __init__(self, db: Database, clock: Clock, audit: AuditService, ttl_minutes: int) -> None:
        self._db, self._clock, self._audit = db, clock, audit
        self._ttl = timedelta(minutes=ttl_minutes)

    # ---- creation (called by the gateway only) --------------------------------------------
    def create_approval(
        self, proposed: ProposedAction, ctx: ActionContext, decision: PolicyDecision, summary: str
    ) -> HumanTask:
        now = self._clock.now()
        return self._insert(
            TaskKind.APPROVAL, TaskStatus.PENDING, proposed, ctx, decision, summary, {},
            expires_at=now + self._ttl,
        )

    def create_escalation(
        self, proposed: ProposedAction, ctx: ActionContext, decision: PolicyDecision,
        summary: str, brief: dict[str, Any],
    ) -> HumanTask:
        return self._insert(
            TaskKind.ESCALATION, TaskStatus.OPEN, proposed, ctx, decision, summary, brief,
            expires_at=None,
        )

    def _insert(self, kind, status, proposed, ctx, decision, summary, brief, expires_at) -> HumanTask:
        row = HumanTaskRow(
            id=f"{'apr' if kind is TaskKind.APPROVAL else 'esc'}_{uuid.uuid4().hex[:20]}",
            kind=kind.value, status=status.value, merchant_id=ctx.merchant_id,
            session_id=ctx.session_id, tool_name=proposed.tool, params=decision.params or {},
            proposed_by=proposed.proposed_by.value, action_hash=decision.action_hash or "",
            tier=int(decision.tier or 0), risk_score=decision.risk.score, summary=summary,
            brief=brief, created_at=self._clock.now(), expires_at=expires_at,
        )
        with self._db.session() as s:
            s.add(row)
        self._audit.record(
            f"human_task.created.{kind.value.lower()}", "SYSTEM", session_id=ctx.session_id,
            merchant_id=ctx.merchant_id, tool_name=proposed.tool,
            payload={"task_id": row.id, "summary": summary},
        )
        return HumanTask.model_validate(row)

    # ---- queries --------------------------------------------------------------------------
    def get(self, task_id: str) -> HumanTask:
        with self._db.session() as s:
            row = s.get(HumanTaskRow, task_id)
            if row is None:
                raise NotFound("task not found")
            return HumanTask.model_validate(row)

    def list(self, kind: TaskKind, status: TaskStatus | None = None) -> list[HumanTask]:
        stmt = select(HumanTaskRow).where(HumanTaskRow.kind == kind.value)
        if status:
            stmt = stmt.where(HumanTaskRow.status == status.value)
        with self._db.session() as s:
            rows = s.scalars(stmt.order_by(HumanTaskRow.created_at.desc()).limit(200))
            return [HumanTask.model_validate(r) for r in rows]

    # ---- operator decisions ---------------------------------------------------------------
    def decide(self, task_id: str, operator_id: str, approve: bool, note: str | None) -> HumanTask:
        task = self.get(task_id)
        if task.kind is not TaskKind.APPROVAL:
            raise Forbidden("escalations are resolved via close, not approve/reject")
        if task.status is not TaskStatus.PENDING:
            raise Conflict(f"task is {task.status.value}, not PENDING")
        now = self._clock.now()
        if task.expires_at and task.expires_at <= now:
            self._set_status(task_id, TaskStatus.EXPIRED, TaskStatus.PENDING, None)
            raise Conflict("approval request has expired")
        new = TaskStatus.APPROVED if approve else TaskStatus.REJECTED
        self._transition(task_id, TaskStatus.PENDING, new, operator_id)
        self._audit.record(
            f"human_task.{new.value.lower()}", "OPERATOR", session_id=task.session_id,
            merchant_id=task.merchant_id, tool_name=task.tool_name,
            payload={"task_id": task_id, "operator_id": operator_id, "note": note},
        )
        return self.get(task_id)

    def close_escalation(self, task_id: str, operator_id: str, note: str | None) -> HumanTask:
        task = self.get(task_id)
        if task.kind is not TaskKind.ESCALATION:
            raise Forbidden("not an escalation")
        self._transition(task_id, TaskStatus.OPEN, TaskStatus.CLOSED, operator_id)
        self._audit.record(
            "human_task.closed", "OPERATOR", session_id=task.session_id,
            merchant_id=task.merchant_id, payload={"task_id": task_id, "note": note,
                                                    "operator_id": operator_id},
        )
        return self.get(task_id)

    # ---- single-use consumption (called by the gateway only) -------------------------------
    def consume_approval(self, task_id: str, action_hash: str, merchant_id: str) -> None:
        """Atomically APPROVED -> EXECUTING, only if hash/merchant match and not expired."""
        with self._db.session() as s:
            res = s.execute(
                update(HumanTaskRow)
                .where(
                    HumanTaskRow.id == task_id,
                    HumanTaskRow.kind == TaskKind.APPROVAL.value,
                    HumanTaskRow.status == TaskStatus.APPROVED.value,
                    HumanTaskRow.action_hash == action_hash,
                    HumanTaskRow.merchant_id == merchant_id,
                    HumanTaskRow.expires_at > self._clock.now(),
                )
                .values(status=TaskStatus.EXECUTING.value)
            )
            if res.rowcount != 1:
                raise Conflict("approval is invalid, expired, mismatched or already used")

    def finish(self, task_id: str, status: TaskStatus) -> None:
        self._set_status(task_id, status, TaskStatus.EXECUTING, None)

    def supersede(self, task_id: str) -> None:
        self._set_status(task_id, TaskStatus.SUPERSEDED, TaskStatus.APPROVED, None)

    # ---- helpers --------------------------------------------------------------------------
    def _transition(self, task_id: str, frm: TaskStatus, to: TaskStatus, operator: str) -> None:
        with self._db.session() as s:
            res = s.execute(
                update(HumanTaskRow)
                .where(HumanTaskRow.id == task_id, HumanTaskRow.status == frm.value)
                .values(status=to.value, decided_by=operator, decided_at=self._clock.now())
            )
            if res.rowcount != 1:
                raise Conflict("task state changed concurrently")

    def _set_status(self, task_id: str, to: TaskStatus, frm: TaskStatus, operator: str | None):
        with self._db.session() as s:
            s.execute(
                update(HumanTaskRow)
                .where(HumanTaskRow.id == task_id, HumanTaskRow.status == frm.value)
                .values(status=to.value)
            )
