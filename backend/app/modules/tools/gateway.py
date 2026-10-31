"""ToolGateway: the ONLY path to any tool. Every call is policy-checked, risk-assessed, audited.

Nothing outside this class holds a reference to tool handlers, so the planner/LLM cannot execute
anything directly. Fail-closed: any error in risk lookup or policy results in DENY/FAILED.
"""
from __future__ import annotations

import logging
from typing import Any

from app.modules.approvals.service import HumanTaskService
from app.modules.audit.service import AuditService
from app.modules.policy.engine import PolicyEngine
from app.modules.tools.base import RiskSignalProvider
from app.modules.tools.brief import build_brief
from app.modules.tools.registry import ToolRegistry
from app.schemas.domain import (
    Actor,
    ActionContext,
    PolicyDecision,
    ProposedAction,
    TaskStatus,
    ToolOutcome,
    ToolStatus,
    Verdict,
)

log = logging.getLogger(__name__)


class ToolGateway:
    def __init__(
        self,
        registry: ToolRegistry,
        policy: PolicyEngine,
        risk_signals: RiskSignalProvider,
        tasks: HumanTaskService,
        audit: AuditService,
    ) -> None:
        self._registry, self._policy, self._risk_signals = registry, policy, risk_signals
        self._tasks, self._audit = tasks, audit

    def execute(
        self, proposed: ProposedAction, ctx: ActionContext, *, approval_id: str | None = None,
        approved_by: str | None = None,
    ) -> ToolOutcome:
        decision = self._decide(proposed, ctx)
        self._audit.record(
            "policy.decision", proposed.proposed_by.value, session_id=ctx.session_id,
            merchant_id=ctx.merchant_id, tool_name=proposed.tool, decision=decision.verdict.value,
            tier=int(decision.tier) if decision.tier else None, risk_score=decision.risk.score,
            payload={"reasons": decision.reasons, "params": decision.params,
                     "rationale": proposed.rationale, "approval_id": approval_id},
        )
        out = dict(tool=proposed.tool, tier=decision.tier, risk_score=decision.risk.score,
                   reasons=decision.reasons)

        if decision.verdict is Verdict.DENY:
            return ToolOutcome(status=ToolStatus.DENIED, **out)

        if decision.verdict is Verdict.ESCALATE:
            if approval_id:  # an approved task whose risk was re-assessed upward
                self._tasks.supersede(approval_id)
            task = self._tasks.create_escalation(
                proposed, ctx, decision, summary=f"Escalation: {proposed.tool}",
                brief=build_brief(proposed, decision, self._audit.list_events(ctx.session_id, 50)),
            )
            return ToolOutcome(status=ToolStatus.ESCALATED, human_task_id=task.id, **out)

        if decision.verdict is Verdict.REQUIRE_APPROVAL:
            if approval_id is None:
                task = self._tasks.create_approval(
                    proposed, ctx, decision, summary=f"Approve {proposed.tool}?"
                )
                return ToolOutcome(status=ToolStatus.PENDING_APPROVAL, human_task_id=task.id, **out)
            try:
                self._tasks.consume_approval(approval_id, decision.action_hash or "", ctx.merchant_id)
            except Exception as exc:  # approval invalid/expired/mismatched/reused
                self._audit.record(
                    "approval.rejected", "SYSTEM", session_id=ctx.session_id,
                    merchant_id=ctx.merchant_id, tool_name=proposed.tool,
                    payload={"approval_id": approval_id, "error": str(exc)},
                )
                return ToolOutcome(status=ToolStatus.DENIED, **{**out, "reasons": ["approval_invalid"]})

        return self._run(proposed, ctx, decision, approval_id, approved_by, out)

    # ------------------------------------------------------------------------------------
    def _decide(self, proposed: ProposedAction, ctx: ActionContext) -> PolicyDecision:
        try:
            txn_id = proposed.params.get("txn_id")
            signals = self._risk_signals.signals_for(
                ctx.merchant_id, txn_id if isinstance(txn_id, str) else None
            )
            calls = self._audit.count(ctx.session_id, "policy.decision")
            return self._policy.evaluate(proposed, ctx, signals, calls)
        except Exception:  # fail closed
            log.exception("policy evaluation failed", extra={"tool": proposed.tool})
            return PolicyDecision(verdict=Verdict.DENY, tier=None, reasons=["policy_unavailable"])

    def _run(self, proposed, ctx, decision, approval_id, approved_by, out) -> ToolOutcome:
        spec = self._registry.get(proposed.tool)
        assert spec is not None and spec.handler is not None  # matrix/registry checked at startup
        try:
            params = spec.params_model.model_validate(decision.params)
            result: dict[str, Any] = spec.handler(ctx.merchant_id, params)
        except Exception as exc:
            log.exception("tool failed", extra={"tool": proposed.tool})
            if approval_id:
                self._tasks.finish(approval_id, TaskStatus.FAILED)
            self._audit.record(
                "tool.failed", Actor.SYSTEM.value, session_id=ctx.session_id,
                merchant_id=ctx.merchant_id, tool_name=proposed.tool,
                payload={"error_type": type(exc).__name__},
            )
            return ToolOutcome(status=ToolStatus.FAILED, **{**out, "reasons": ["tool_error"]})
        if approval_id:
            self._tasks.finish(approval_id, TaskStatus.EXECUTED)
        self._audit.record(
            "tool.executed", Actor.SYSTEM.value, session_id=ctx.session_id,
            merchant_id=ctx.merchant_id, tool_name=proposed.tool, tier=int(decision.tier or 0),
            payload={"result": result, "approved_by": approved_by},
        )
        return ToolOutcome(status=ToolStatus.EXECUTED, result=result, **out)


