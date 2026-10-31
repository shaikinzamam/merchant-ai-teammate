"""Typed domain contracts shared across modules. No business logic here."""
from __future__ import annotations

from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Language(StrEnum):
    EN = "en"
    HI = "hi"
    TE = "te"
    KN = "kn"


class Intent(StrEnum):
    SETTLEMENT_STATUS = "settlement_status"
    QR_REISSUE = "qr_reissue"
    SOUNDBOX_ISSUE = "soundbox_issue"
    DISPUTE = "dispute"
    TECHNICIAN = "technician"
    FAQ = "faq"
    FRAUD_CONCERN = "fraud_concern"
    KYC_ISSUE = "kyc_issue"
    CHURN_THREAT = "churn_threat"
    UNKNOWN = "unknown"


class RiskTier(IntEnum):
    AUTONOMOUS = 1   # Tier 1: low risk, executes automatically
    HUMAN_CHECK = 2  # Tier 2: medium risk, needs human approval
    ESCALATION = 3   # Tier 3: high risk, escalate to a human with a brief


class Verdict(StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    ESCALATE = "ESCALATE"
    DENY = "DENY"


class ToolStatus(StrEnum):
    EXECUTED = "EXECUTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ESCALATED = "ESCALATED"
    DENIED = "DENIED"
    FAILED = "FAILED"


class Actor(StrEnum):
    SYSTEM = "SYSTEM"
    PLANNER = "PLANNER"
    GROWTH = "GROWTH"
    OPERATOR = "OPERATOR"
    MERCHANT = "MERCHANT"


class TaskKind(StrEnum):
    APPROVAL = "APPROVAL"
    ESCALATION = "ESCALATION"


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"  # approval invalidated because risk re-assessment escalated it
    OPEN = "OPEN"              # escalation awaiting a human
    CLOSED = "CLOSED"


class EscalationReason(StrEnum):
    ACCOUNT_TAKEOVER_OR_FRAUD = "ACCOUNT_TAKEOVER_OR_FRAUD"
    REPEATED_KYC_FAILURE = "REPEATED_KYC_FAILURE"
    SEVERE_CHARGEBACK = "SEVERE_CHARGEBACK"
    CHURN_THREAT = "CHURN_THREAT"
    RISK_POLICY = "RISK_POLICY"


# ---- planning -----------------------------------------------------------------------------


class PlannedStep(BaseModel):
    """A step proposed by a planner. UNTRUSTED: tool/params may be arbitrary (e.g. LLM output)."""

    model_config = ConfigDict(extra="ignore")
    tool: str = Field(max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field("", max_length=300)


class Plan(BaseModel):
    intent: Intent = Intent.UNKNOWN
    confidence: float = Field(0.0, ge=0, le=1)
    steps: list[PlannedStep] = Field(default_factory=list)
    clarification: str | None = None  # template key asking the merchant for missing info
    source: str = "rules"


class ToolDescriptor(BaseModel):
    name: str
    description: str
    params_schema: dict[str, Any]


class MerchantSummary(BaseModel):
    """Minimal, non-PII merchant context handed to the planner."""

    preferred_language: str = "en"
    has_soundbox: bool = False
    has_edc: bool = False
    kyc_status: str = "UNKNOWN"


# ---- policy & risk ------------------------------------------------------------------------


class ProposedAction(BaseModel):
    model_config = ConfigDict(frozen=True)
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    proposed_by: Actor
    rationale: str = ""


class ActionContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    session_id: str
    merchant_id: str


class RiskSignals(BaseModel):
    """Facts from the system of record (never from the LLM or the merchant's message)."""

    fraud_flag: bool = False
    kyc_failed_attempts: int = 0
    open_chargebacks: int = 0
    bank_account_changed_days_ago: int | None = None
    target_txn_amount_inr: int | None = None


class RiskAssessment(BaseModel):
    score: int = 0
    signals: list[str] = Field(default_factory=list)
    minimum_tier: RiskTier = RiskTier.AUTONOMOUS


class PolicyDecision(BaseModel):
    verdict: Verdict
    tier: RiskTier | None
    risk: RiskAssessment = Field(default_factory=RiskAssessment)
    reasons: list[str] = Field(default_factory=list)
    params: dict[str, Any] | None = None  # validated & normalised params
    action_hash: str | None = None


class ToolOutcome(BaseModel):
    tool: str
    status: ToolStatus
    tier: RiskTier | None = None
    risk_score: int | None = None
    reasons: list[str] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    human_task_id: str | None = None


class HumanTask(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: TaskKind
    status: TaskStatus
    merchant_id: str
    session_id: str
    tool_name: str
    params: dict[str, Any]
    proposed_by: Actor
    action_hash: str
    tier: int
    risk_score: int
    summary: str
    brief: dict[str, Any]
    created_at: datetime
    expires_at: datetime | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
