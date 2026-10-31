"""The tiered permission matrix: THE source of truth for what each tool may do.

Default deny: any tool not listed here cannot be executed. Tiers mirror the pitch deck:
Tier 1 autonomous · Tier 2 human approval · Tier 3 escalate.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from app.schemas.domain import RiskTier


@dataclass(frozen=True)
class ActionPolicy:
    tier: RiskTier
    side_effect: bool
    # If False, risk signals never raise the tier (used for own-data reads / the escalate action
    # itself, otherwise a flagged merchant would block the very context needed to escalate).
    risk_sensitive: bool = True


T1, T2, T3 = RiskTier.AUTONOMOUS, RiskTier.HUMAN_CHECK, RiskTier.ESCALATION

POLICY_MATRIX = MappingProxyType(
    {
        "get_merchant_context": ActionPolicy(T1, side_effect=False, risk_sensitive=False),
        "check_settlement_status": ActionPolicy(T1, side_effect=False),
        "track_dispute": ActionPolicy(T1, side_effect=False),
        "soundbox_diagnostics": ActionPolicy(T1, side_effect=False),
        "lookup_faq": ActionPolicy(T1, side_effect=False),
        "reissue_qr": ActionPolicy(T1, side_effect=True),
        "file_dispute": ActionPolicy(T2, side_effect=True),
        "dispatch_technician": ActionPolicy(T2, side_effect=True),
        "check_bank_account_change": ActionPolicy(T2, side_effect=False),
        "create_crm_lead": ActionPolicy(T2, side_effect=True),
        "escalate_to_human": ActionPolicy(T3, side_effect=True, risk_sensitive=False),
    }
)
