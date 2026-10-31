from app.core.errors import Conflict
from app.schemas.domain import ActionContext, Actor, ProposedAction, TaskStatus, ToolStatus

CTX = ActionContext(session_id="s_gateway1", merchant_id="M1001")


def propose(tool, params=None):
    return ProposedAction(tool=tool, params=params or {}, proposed_by=Actor.PLANNER)


def test_tier1_executes_and_is_audited(container):
    out = container.gateway.execute(propose("check_settlement_status", {"day": "YESTERDAY"}), CTX)
    assert out.status is ToolStatus.EXECUTED and out.result["status"] == "DELAYED"
    assert out.result["_source"] == "MOCK_PAYTM"
    kinds = [e.event_type for e in container.audit.list_events("s_gateway1")]
    assert kinds == ["policy.decision", "tool.executed"]


def test_tier2_waits_for_approval_and_does_not_execute(container):
    out = container.gateway.execute(propose("dispatch_technician", {"issue": "no sound"}), CTX)
    assert out.status is ToolStatus.PENDING_APPROVAL and out.result is None
    assert container.integration.leads == [] and out.human_task_id


def test_approval_executes_once_then_cannot_be_reused(container):
    out = container.gateway.execute(propose("create_crm_lead",
            {"product": "SOUNDBOX", "intent_score": 70}), CTX)
    task, result = container.approvals.approve(out.human_task_id, "op1", None)
    assert result.status is ToolStatus.EXECUTED and task.status is TaskStatus.EXECUTED
    assert len(container.integration.leads) == 1
    with __import__("pytest").raises(Conflict):
        container.approvals.approve(out.human_task_id, "op1", None)
    replay = container.gateway.execute(propose("create_crm_lead",
            {"product": "SOUNDBOX", "intent_score": 70}), CTX, approval_id=out.human_task_id)
    assert replay.status is ToolStatus.DENIED and len(container.integration.leads) == 1


def test_approval_is_bound_to_exact_params(container):
    out = container.gateway.execute(propose("create_crm_lead",
            {"product": "SOUNDBOX", "intent_score": 70}), CTX)
    container.tasks.decide(out.human_task_id, "op1", True, None)
    tampered = container.gateway.execute(propose("create_crm_lead",
            {"product": "EDC", "intent_score": 99}), CTX, approval_id=out.human_task_id)
    assert tampered.status is ToolStatus.DENIED and container.integration.leads == []


def test_approval_expires(container, clock):
    from datetime import timedelta
    out = container.gateway.execute(propose("dispatch_technician", {"issue": "x"}), CTX)
    clock.set(clock.now() + timedelta(minutes=31))
    with __import__("pytest").raises(Conflict):
        container.approvals.approve(out.human_task_id, "op1", None)


def test_tier3_escalates_with_brief_and_never_executes(container):
    out = container.gateway.execute(
        propose("escalate_to_human", {"reason": "ACCOUNT_TAKEOVER_OR_FRAUD"}), CTX)
    assert out.status is ToolStatus.ESCALATED
    task = container.tasks.get(out.human_task_id)
    assert task.brief["why_escalated"] and task.kind.value == "ESCALATION"


def test_unknown_tool_is_denied_and_audited(container):
    out = container.gateway.execute(propose("wire_money", {"to": "x"}), CTX)
    assert out.status is ToolStatus.DENIED
    assert container.audit.list_events("s_gateway1")[0].decision == "DENY"


def test_risk_provider_failure_fails_closed(container, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("risk backend down")
    monkeypatch.setattr(container.gateway._risk_signals, "signals_for", boom)
    out = container.gateway.execute(propose("check_settlement_status"), CTX)
    assert out.status is ToolStatus.DENIED and "policy_unavailable" in out.reasons


def test_audit_chain_detects_tampering(container):
    container.gateway.execute(propose("check_settlement_status"), CTX)
    assert container.audit.verify_chain().valid
    from app.database.models import AuditEventRow
    with container.db.session() as s:
        row = s.query(AuditEventRow).first()
        row.payload = {"reasons": ["edited"]}
    v = container.audit.verify_chain()
    assert not v.valid and v.first_invalid_seq == 1
