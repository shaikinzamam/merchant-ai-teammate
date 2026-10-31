"""Deterministic risk engine. It can only RAISE the tier of an action, never lower it."""
from __future__ import annotations

from typing import Any

from app.modules.policy.matrix import ActionPolicy
from app.schemas.domain import RiskAssessment, RiskSignals, RiskTier

TIER3_SCORE = 70
TIER2_SCORE = 30
HIGH_VALUE_DISPUTE_INR = 100_000  # PLACEHOLDER threshold for "severe chargeback"


class RiskEngine:
    def assess(
        self, tool: str, params: dict[str, Any], signals: RiskSignals, rule: ActionPolicy
    ) -> RiskAssessment:
        if not rule.risk_sensitive:
            return RiskAssessment()

        score, tags = 0, []

        def add(points: int, tag: str) -> None:
            nonlocal score
            score += points
            tags.append(tag)

        if signals.fraud_flag:
            add(100, "merchant_fraud_flag")
        if signals.kyc_failed_attempts >= 3:
            add(90, "repeated_kyc_failure")
        if signals.open_chargebacks >= 3:
            add(80, "multiple_open_chargebacks")
        if (
            tool == "file_dispute"
            and (signals.target_txn_amount_inr or 0) >= HIGH_VALUE_DISPUTE_INR
        ):
            add(85, "high_value_dispute")
        if (
            signals.bank_account_changed_days_ago is not None
            and signals.bank_account_changed_days_ago < 7
            and rule.side_effect
        ):
            add(30, "recent_bank_account_change")

        score = min(score, 100)
        tier = (
            RiskTier.ESCALATION
            if score >= TIER3_SCORE
            else RiskTier.HUMAN_CHECK
            if score >= TIER2_SCORE
            else RiskTier.AUTONOMOUS
        )
        return RiskAssessment(score=score, signals=tags, minimum_tier=tier)
