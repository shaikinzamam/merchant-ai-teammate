"""Disabled voice-provider implementation."""
from __future__ import annotations

from app.core.errors import NotAvailableError
from app.modules.voice.schemas import SynthesizedAudio, Transcript
from app.schemas.domain import Language


class DisabledVoiceService:
    def transcribe(self, audio: bytes, filename: str, content_type: str) -> Transcript:
        raise NotAvailableError("Voice is not enabled")

    def synthesize(self, text: str, language: Language) -> SynthesizedAudio:
        raise NotAvailableError("Voice is not enabled")
