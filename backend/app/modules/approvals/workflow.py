"""Operator-facing approval workflow. Approving re-submits the action through the gateway, which
re-runs policy + risk (so a changed risk picture can still escalate or deny it)."""
from __future__ import annotations

from app.modules.approvals.service import HumanTaskService
from app.modules.tools.gateway import ToolGateway
from app.schemas.domain import ActionContext, Actor, HumanTask, ProposedAction, ToolOutcome


class ApprovalWorkflow:
    def __init__(self, tasks: HumanTaskService, gateway: ToolGateway) -> None:
        self._tasks, self._gateway = tasks, gateway

    def approve(self, task_id: str, operator_id: str, note: str | None) -> tuple[HumanTask, ToolOutcome]:
        task = self._tasks.decide(task_id, operator_id, True, note)
        proposed = ProposedAction(tool=task.tool_name, params=task.params,
                                  proposed_by=Actor(task.proposed_by),
                                  rationale=f"approved by {operator_id}")
        outcome = self._gateway.execute(
            proposed, ActionContext(session_id=task.session_id, merchant_id=task.merchant_id),
            approval_id=task.id, approved_by=operator_id,
        )
        return self._tasks.get(task_id), outcome

    def reject(self, task_id: str, operator_id: str, note: str | None) -> HumanTask:
        return self._tasks.decide(task_id, operator_id, False, note)
