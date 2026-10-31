"""Typed parameter schemas for every tool. extra='forbid' blocks smuggled fields."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.domain import EscalationReason


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NoParams(_Params):
    pass


class SettlementParams(_Params):
    day: Literal["TODAY", "YESTERDAY"] = "YESTERDAY"


class TrackDisputeParams(_Params):
    dispute_id: str = Field(pattern=r"^DSP[A-Z0-9]{6,20}$")


class SoundboxDiagParams(_Params):
    device_id: str | None = Field(None, pattern=r"^[A-Z0-9_-]{4,32}$")


class FaqParams(_Params):
    topic: Literal[
        "settlement_timing", "qr_help", "soundbox_setup", "dispute_process", "kyc_process"
    ]


class ReissueQrParams(_Params):
    reason: Literal["DAMAGED", "LOST", "NAME_CHANGE"] = "DAMAGED"


class FileDisputeParams(_Params):
    txn_id: str = Field(pattern=r"^TXN[A-Z0-9]{6,20}$")
    reason: Literal["NOT_RECEIVED", "DUPLICATE_DEBIT", "WRONG_AMOUNT", "OTHER"] = "OTHER"


class DispatchTechnicianParams(_Params):
    device_id: str | None = Field(None, pattern=r"^[A-Z0-9_-]{4,32}$")
    issue: str = Field(max_length=300)
    preferred_slot: Literal["MORNING", "AFTERNOON", "EVENING"] = "MORNING"


class BankChangeCheckParams(_Params):
    change_type: Literal["IFSC_UPDATE", "ACCOUNT_CHANGE"] = "ACCOUNT_CHANGE"


class CreateCrmLeadParams(_Params):
    product: Literal["SOUNDBOX", "EDC", "LOAN"]
    intent_score: int = Field(ge=0, le=100)
    notes: str = Field("", max_length=300)


class EscalateParams(_Params):
    reason: EscalationReason
    details: str = Field("", max_length=500)
