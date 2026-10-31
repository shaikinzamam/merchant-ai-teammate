from app.modules.policy.matrix import POLICY_MATRIX
from app.schemas.domain import (
    ActionContext, Actor, ProposedAction, RiskSignals, RiskTier, Verdict,
)

CTX = ActionContext(session_id="s_test0001", merchant_id="M1001")


def ev(container, tool, params=None, signals=None, calls=0, ctx=CTX):
    action = ProposedAction(tool=tool, params=params or {}, proposed_by=Actor.PLANNER)
    return container.gateway._policy.evaluate(action, ctx, signals or RiskSignals(), calls)


def test_every_registered_tool_has_a_policy(container):
    assert container.registry.names() == set(POLICY_MATRIX)


def test_unknown_tool_is_denied(container):
    d = ev(container, "transfer_funds", {"amount": 1})
    assert d.verdict is Verdict.DENY and "unknown_or_unlisted_tool" in d.reasons


def test_tiers_match_the_deck(container):
    assert ev(container, "check_settlement_status").verdict is Verdict.ALLOW
    assert ev(container, "dispatch_technician", {"issue": "x"}).verdict is Verdict.REQUIRE_APPROVAL
    d = ev(container, "escalate_to_human", {"reason": "CHURN_THREAT"})
    assert d.verdict is Verdict.ESCALATE


def test_extra_or_invalid_params_denied(container):
    assert ev(container, "check_settlement_status", {"day": "TODAY", "x": 1}).verdict is Verdict.DENY
    assert ev(container, "file_dispute", {"txn_id": "bad"}).verdict is Verdict.DENY


def test_cross_merchant_param_denied(container):
    d = ev(container, "check_settlement_status", {"merchant_id": "M9999"})
    assert d.verdict is Verdict.DENY and "cross_merchant_access_attempt" in d.reasons


def test_fraud_flag_raises_tier_one_action_to_escalation(container):
    d = ev(container, "check_settlement_status", signals=RiskSignals(fraud_flag=True))
    assert d.verdict is Verdict.ESCALATE and d.tier is RiskTier.ESCALATION


def test_risk_never_lowers_tier(container):
    d = ev(container, "file_dispute", {"txn_id": "TXN100001"}, RiskSignals())
    assert d.tier is RiskTier.HUMAN_CHECK


def test_high_value_dispute_escalates_and_recent_bank_change_needs_approval(container):
    big = ev(container, "file_dispute", {"txn_id": "TXN100002"},
             RiskSignals(target_txn_amount_inr=250_000))
    assert big.verdict is Verdict.ESCALATE
    qr = ev(container, "reissue_qr", signals=RiskSignals(bank_account_changed_days_ago=2))
    assert qr.verdict is Verdict.REQUIRE_APPROVAL


def test_session_budget_enforced(container):
    d = ev(container, "check_settlement_status", calls=container.settings.max_tool_calls_per_session)
    assert d.verdict is Verdict.DENY
