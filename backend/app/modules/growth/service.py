"""Growth module: turns resolved support interactions into *proposed* CRM leads.
It never creates a lead itself; it proposes a step that must still clear policy (Tier 2)."""
from __future__ import annotations

from typing import Any

from app.schemas.domain import Intent, PlannedStep

_ELIGIBLE = {Intent.SETTLEMENT_STATUS, Intent.SOUNDBOX_ISSUE, Intent.QR_REISSUE, Intent.FAQ}


class GrowthService:
    def __init__(self, soundbox_min_volume_inr: int, edc_min_volume_inr: int) -> None:
        self._sb, self._edc = soundbox_min_volume_inr, edc_min_volume_inr

    def propose(self, intent: Intent, context: dict[str, Any]) -> PlannedStep | None:
        if intent not in _ELIGIBLE:
            return None
        volume = int(context.get("avg_daily_volume_inr", 0))
        if not context.get("has_edc") and volume >= self._edc:
            product = "EDC"
        elif not context.get("has_soundbox") and volume >= self._sb:
            product = "SOUNDBOX"
        else:
            return None
        score = min(100, 50 + volume * 50 // max(self._edc, 1))
        return PlannedStep(
            tool="create_crm_lead",
            params={"product": product, "intent_score": score,
                    "notes": f"avg daily volume INR {volume}; trigger intent={intent.value}"},
            rationale="growth opportunity from resolved support query",
        )
