"""Deterministic, offline planner (keyword-based). Used as the default and as the LLM fallback."""
from __future__ import annotations

import re

from app.schemas.domain import (
    EscalationReason as ER,
    Intent,
    Language,
    MerchantSummary,
    Plan,
    PlannedStep,
    ToolDescriptor,
)

_TXN = re.compile(r"\bTXN[A-Z0-9]{6,20}\b", re.IGNORECASE)

# Order = priority (safety-relevant intents first).
_KEYWORDS: list[tuple[Intent, tuple[str, ...]]] = [
    (Intent.FRAUD_CONCERN, ("fraud", "hack", "scam", "unauthorized", "unauthorised", "stolen",
                            "dhokha", "फ्रॉड", "धोखा", "ठगी", "మోసం", "ಮೋಸ")),
    (Intent.KYC_ISSUE, ("kyc", "केवाईसी")),
    (Intent.CHURN_THREAT, ("close my account", "leave paytm", "switch to", "band kar", "बंद कर")),
    (Intent.DISPUTE, ("dispute", "chargeback", "double debit", "duplicate", "डिस्प्यूट", "चार्जबैक")),
    (Intent.TECHNICIAN, ("technician", "engineer", "install", "टेक्नीशियन", "तकनीशियन")),
    (Intent.QR_REISSUE, ("qr", "क्यूआर")),
    (Intent.SOUNDBOX_ISSUE, ("soundbox", "sound box", "साउंडबॉक्स", "speaker")),
    (Intent.SETTLEMENT_STATUS, ("settlement", "सेटलमेंट", "సెటిల్‌మెంట్", "సెటిల్మెంట్",
                                "ಸೆಟಲ್‌ಮೆಂಟ್", "ಸೆಟಲ್ಮೆಂಟ್", "paisa", "पैसा")),
    (Intent.FAQ, ("how", "kaise", "process", "कैसे")),
]
_YESTERDAY = ("kal", "yesterday", "कल", "నిన్న", "ನಿನ್ನೆ")
_ESCALATIONS = {
    Intent.FRAUD_CONCERN: ER.ACCOUNT_TAKEOVER_OR_FRAUD,
    Intent.KYC_ISSUE: ER.REPEATED_KYC_FAILURE,
    Intent.CHURN_THREAT: ER.CHURN_THREAT,
}
_SAFETY_INTENTS = set(_ESCALATIONS)


class RuleBasedPlanner:
    name = "rules"

    def plan(
        self, message: str, language: Language, merchant: MerchantSummary,
        tools: list[ToolDescriptor],
    ) -> Plan:
        text = message.lower()
        intent = next(
            (i for i, kws in _KEYWORDS if any(k in text for k in kws)), Intent.UNKNOWN
        )

        def plan(*steps: PlannedStep, clarification: str | None = None) -> Plan:
            return Plan(intent=intent, confidence=0.6 if intent != Intent.UNKNOWN else 0.0,
                        steps=list(steps), clarification=clarification, source=self.name)

        if intent in _ESCALATIONS:
            return plan(PlannedStep(
                tool="escalate_to_human",
                params={"reason": _ESCALATIONS[intent].value, "details": message[:500]},
                rationale=f"intent={intent.value}"))
        if intent is Intent.SETTLEMENT_STATUS:
            day = "YESTERDAY" if any(k in text for k in _YESTERDAY) else "TODAY"
            return plan(PlannedStep(tool="check_settlement_status", params={"day": day}))
        if intent is Intent.QR_REISSUE:
            return plan(PlannedStep(tool="reissue_qr", params={"reason": "DAMAGED"}))
        if intent is Intent.SOUNDBOX_ISSUE:
            return plan(PlannedStep(tool="soundbox_diagnostics", params={}))
        if intent is Intent.TECHNICIAN:
            return plan(PlannedStep(tool="dispatch_technician",
                                    params={"issue": message[:300], "preferred_slot": "MORNING"}))
        if intent is Intent.DISPUTE:
            m = _TXN.search(message)
            if not m:
                return plan(clarification="need_txn_id")
            reason = "DUPLICATE_DEBIT" if ("double" in text or "duplicate" in text) else "OTHER"
            return plan(PlannedStep(tool="file_dispute",
                                    params={"txn_id": m.group(0).upper(), "reason": reason}))
        if intent is Intent.FAQ:
            return plan(PlannedStep(tool="lookup_faq", params={"topic": "settlement_timing"}))
        return plan()
