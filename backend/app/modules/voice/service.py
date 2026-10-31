"""Voice provider contract."""
from __future__ import annotations

from typing import Protocol

from app.modules.voice.schemas import SynthesizedAudio, Transcript
from app.schemas.domain import Language


class VoiceService(Protocol):
    def transcribe(self, audio: bytes, filename: str, content_type: str) -> Transcript: ...
    def synthesize(self, text: str, language: Language) -> SynthesizedAudio: ...
