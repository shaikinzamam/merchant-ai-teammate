"""MOCK Paytm-style tools. SIMULATED ONLY: no network calls, no real Paytm systems.

Every result carries `_source: MOCK_PAYTM`. A real adapter must live in app/integrations/paytm_real
and implement the same ToolIntegration protocol; the rest of the system will not change.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from app.core.clock import Clock
from app.core.errors import NotFound
from app.integrations.mock_paytm.data import FAQ, seed_merchants, seed_transactions
from app.modules.tools import schemas as S
from app.modules.tools.base import RiskSignalProvider, ToolSpec
from app.schemas.domain import RiskSignals

_SRC = {"_source": "MOCK_PAYTM"}


def _id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:10].upper()}"


class MockRiskSignals:
    def __init__(self, backend: MockPaytmIntegration) -> None:
        self._b = backend

    def signals_for(self, merchant_id: str, txn_id: str | None) -> RiskSignals:
        m = self._b.merchants.get(merchant_id)
        if m is None:
            raise NotFound("merchant not found")
        txn = self._b.transactions.get(txn_id) if txn_id else None
        return RiskSignals(
            fraud_flag=m.fraud_flag, kyc_failed_attempts=m.kyc_failed_attempts,
            open_chargebacks=m.open_chargebacks,
            bank_account_changed_days_ago=m.bank_account_changed_days_ago,
            target_txn_amount_inr=txn.amount_inr if txn and txn.merchant_id == merchant_id else None,
        )


class MockPaytmIntegration:
    name = "mock_paytm"
    is_simulated = True

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self.merchants = seed_merchants()
        self.transactions = seed_transactions()
        self.disputes: dict[str, dict[str, Any]] = {}
        self.leads: list[dict[str, Any]] = []

    def risk_signals(self) -> RiskSignalProvider:
        return MockRiskSignals(self)

    def _merchant(self, merchant_id: str):
        m = self.merchants.get(merchant_id)
        if m is None:
            raise NotFound("merchant not found")
        return m

    # ---- handlers: (merchant_id, params) -> dict ------------------------------------------
    def get_merchant_context(self, merchant_id: str, _p: S.NoParams) -> dict[str, Any]:
        m = self._merchant(merchant_id)
        return {
            "merchant_id": m.merchant_id, "mid": m.mid, "preferred_language": m.preferred_language,
            "bank_account_status": m.bank_account_status, "kyc_status": m.kyc_status,
            "has_soundbox": m.has_soundbox, "has_edc": m.has_edc,
            "avg_daily_volume_inr": m.avg_daily_volume_inr,
            "avg_daily_txn_count": m.avg_daily_txn_count, "devices": m.devices, **_SRC,
        }

    def check_settlement_status(self, merchant_id: str, p: S.SettlementParams) -> dict[str, Any]:
        m = self._merchant(merchant_id)
        day = self._clock.now().date() - timedelta(days=1 if p.day == "YESTERDAY" else 0)
        base = {"date": day.isoformat(), "amount_inr": max(m.avg_daily_volume_inr, 0), **_SRC}
        if m.merchant_id == "M1001":  # the deck's demo scenario
            return {**base, "status": "DELAYED", "reason": "BANK_HOLIDAY_CLEARING",
                    "expected_by": "11:30 IST"}
        return {**base, "status": "SETTLED", "reason": None, "expected_by": None}

    def track_dispute(self, merchant_id: str, p: S.TrackDisputeParams) -> dict[str, Any]:
        d = self.disputes.get(p.dispute_id)
        if d is None or d["merchant_id"] != merchant_id:
            raise NotFound("dispute not found")
        return {"dispute_id": p.dispute_id, "status": d["status"], **_SRC}

    def soundbox_diagnostics(self, merchant_id: str, p: S.SoundboxDiagParams) -> dict[str, Any]:
        m = self._merchant(merchant_id)
        if not m.has_soundbox:
            return {"status": "NO_DEVICE", **_SRC}
        return {"status": "ONLINE", "battery_pct": 80, "last_sync": "recent", **_SRC}

    def lookup_faq(self, _mid: str, p: S.FaqParams) -> dict[str, Any]:
        return {"topic": p.topic, "answer": FAQ[p.topic], **_SRC}

    def reissue_qr(self, merchant_id: str, p: S.ReissueQrParams) -> dict[str, Any]:
        self._merchant(merchant_id)
        return {"request_id": _id("QRR"), "reason": p.reason, "status": "SUBMITTED", **_SRC}

    def file_dispute(self, merchant_id: str, p: S.FileDisputeParams) -> dict[str, Any]:
        txn = self.transactions.get(p.txn_id)
        if txn is None or txn.merchant_id != merchant_id:
            raise NotFound("transaction not found")
        did = _id("DSP")
        self.disputes[did] = {"merchant_id": merchant_id, "status": "OPEN", "txn_id": p.txn_id}
        return {"dispute_id": did, "status": "OPEN", **_SRC}

    def dispatch_technician(self, merchant_id: str, p: S.DispatchTechnicianParams) -> dict[str, Any]:
        self._merchant(merchant_id)
        return {"ticket_id": _id("TCH"), "slot": p.preferred_slot, "status": "SCHEDULED", **_SRC}

    def check_bank_account_change(self, merchant_id: str, p: S.BankChangeCheckParams) -> dict[str, Any]:
        m = self._merchant(merchant_id)
        return {"change_type": p.change_type, "eligible": m.kyc_status == "VERIFIED", **_SRC}

    def create_crm_lead(self, merchant_id: str, p: S.CreateCrmLeadParams) -> dict[str, Any]:
        self._merchant(merchant_id)
        lead = {"lead_id": _id("LEAD"), "merchant_id": merchant_id, "product": p.product,
                "intent_score": p.intent_score, "notes": p.notes}
        self.leads.append(lead)
        return {"lead_id": lead["lead_id"], "product": p.product, "status": "CREATED", **_SRC}

    # ---- registration ---------------------------------------------------------------------
    def tool_specs(self) -> list[ToolSpec]:
        T = ToolSpec
        return [
            T("get_merchant_context", "Read the authenticated merchant's profile.", S.NoParams,
              self.get_merchant_context),
            T("check_settlement_status", "Check settlement status for today or yesterday.",
              S.SettlementParams, self.check_settlement_status),
            T("track_dispute", "Track the status of an existing dispute.", S.TrackDisputeParams,
              self.track_dispute),
            T("soundbox_diagnostics", "Read Soundbox device diagnostics.", S.SoundboxDiagParams,
              self.soundbox_diagnostics),
            T("lookup_faq", "Look up a policy/FAQ explanation.", S.FaqParams, self.lookup_faq),
            T("reissue_qr", "Request a replacement QR code.", S.ReissueQrParams, self.reissue_qr),
            T("file_dispute", "File a dispute for a transaction (needs approval).",
              S.FileDisputeParams, self.file_dispute),
            T("dispatch_technician", "Schedule a technician visit (needs approval).",
              S.DispatchTechnicianParams, self.dispatch_technician),
            T("check_bank_account_change", "Check bank-account modification eligibility.",
              S.BankChangeCheckParams, self.check_bank_account_change),
            T("create_crm_lead", "Create a sales lead (needs approval).", S.CreateCrmLeadParams,
              self.create_crm_lead),
        ]
