"""Policy engine: validates a proposed action and returns a verdict. Pure + deterministic."""
from __future__ import annotations

from collections.abc import Callable, Mapping

from pydantic import BaseModel, ValidationError

from app.modules.policy.hashing import action_hash
from app.modules.policy.matrix import ActionPolicy
from app.modules.policy.risk import RiskEngine
from app.schemas.domain import (
    ActionContext,
    PolicyDecision,
    ProposedAction,
    RiskSignals,
    RiskTier,
    Verdict,
)

_VERDICT_BY_TIER = {
    RiskTier.AUTONOMOUS: Verdict.ALLOW,
    RiskTier.HUMAN_CHECK: Verdict.REQUIRE_APPROVAL,
    RiskTier.ESCALATION: Verdict.ESCALATE,
}


class PolicyEngine:
    def __init__(
        self,
        matrix: Mapping[str, ActionPolicy],
        params_model_lookup: Callable[[str], type[BaseModel] | None],
        risk_engine: RiskEngine,
        max_calls_per_session: int,
    ) -> None:
        self._matrix = matrix
        self._params_model = params_model_lookup
        self._risk = risk_engine
        self._max_calls = max_calls_per_session

    def evaluate(
        self,
        proposed: ProposedAction,
        ctx: ActionContext,
        signals: RiskSignals,
        calls_so_far: int,
    ) -> PolicyDecision:
        def deny(reason: str) -> PolicyDecision:
            return PolicyDecision(verdict=Verdict.DENY, tier=None, reasons=[reason])

        rule = self._matrix.get(proposed.tool)
        model = self._params_model(proposed.tool)
        if rule is None or model is None:
            return deny("unknown_or_unlisted_tool")
        if calls_so_far >= self._max_calls:
            return deny("session_tool_budget_exceeded")

        raw = dict(proposed.params)
        if "merchant_id" in raw:
            if raw["merchant_id"] != ctx.merchant_id:
                return deny("cross_merchant_access_attempt")
            raw.pop("merchant_id")  # scope always comes from the session, never from params
        try:
            params = model.model_validate(raw).model_dump(mode="json")
        except ValidationError:
            return deny("invalid_parameters")

        risk = self._risk.assess(proposed.tool, params, signals, rule)
        tier = RiskTier(max(rule.tier, risk.minimum_tier))
        reasons = [f"base_tier={int(rule.tier)}", *risk.signals]
        if tier > rule.tier:
            reasons.append(f"tier_raised_by_risk_to_{int(tier)}")
        return PolicyDecision(
            verdict=_VERDICT_BY_TIER[tier],
            tier=tier,
            risk=risk,
            reasons=reasons,
            params=params,
            action_hash=action_hash(proposed.tool, params, ctx.merchant_id),
        )
