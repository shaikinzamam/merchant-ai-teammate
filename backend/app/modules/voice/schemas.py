"""Typed contracts for voice transcription and synthesis."""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas.domain import Language


class Transcript(BaseModel):
    text: str
    language: Language


class SynthesizedAudio(BaseModel):
    content_type: str
    data_base64: str
