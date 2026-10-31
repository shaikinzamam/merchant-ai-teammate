"""HTTP request/response models."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.domain import (
    HumanTask,
    Intent,
    Language,
    RiskTier,
    ToolOutcome,
    ToolStatus,
)
from app.modules.voice.schemas import SynthesizedAudio


class ChatRequest(BaseModel):
    # Prototype: merchant_id is supplied by the caller. In production it must come from an
    # authenticated merchant session/token, never from the request body.
    merchant_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,32}$")
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(None, pattern=r"^[A-Za-z0-9_-]{8,64}$")


class ActionSummary(BaseModel):
    tool: str
    status: ToolStatus
    tier: RiskTier | None
    human_task_id: str | None = None

    @classmethod
    def from_outcome(cls, o: ToolOutcome) -> ActionSummary:
        return cls(tool=o.tool, status=o.status, tier=o.tier, human_task_id=o.human_task_id)


class ChatResponse(BaseModel):
    session_id: str
    language: Language
    intent: Intent
    reply: str
    actions: list[ActionSummary]
    planner: str
    tools_environment: Literal["SIMULATED"] = "SIMULATED"


class VoiceChatResponse(ChatResponse):
    transcript: str
    detected_language: Language
    audio: SynthesizedAudio | None = None


class VoiceSpeakRequest(BaseModel):
    text: str
    language: Language


class VoiceStatusResponse(BaseModel):
    enabled: bool
    provider: Literal["sarvam", "off"]
    stt_model: str
    tts_model: str


class DecisionRequest(BaseModel):
    note: str | None = Field(None, max_length=500)


class ApprovalResult(BaseModel):
    task: HumanTask
    outcome: ToolOutcome | None = None


class ChainVerificationView(BaseModel):
    valid: bool
    events_checked: int
    first_invalid_seq: int | None = None

