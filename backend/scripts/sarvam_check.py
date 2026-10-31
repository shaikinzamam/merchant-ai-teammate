"""Verify Sarvam TTS and STT with an in-memory Hindi audio round trip."""
from __future__ import annotations

import base64

from pydantic import ValidationError

from app.config import get_settings
from app.core.errors import ExternalServiceError
from app.modules.language.service import MockLanguageService
from app.modules.voice.sarvam import SarvamVoiceService
from app.schemas.domain import Language

_CHECK_TEXT = "नमस्ते, आपका सेटलमेंट आज मिल जाएगा।"


def main() -> int:
    try:
        settings = get_settings()
    except ValidationError:
        print("Configuration is invalid; check the project .env.")
        return 1

    if not settings.sarvam_api_key or not settings.sarvam_api_key.get_secret_value().strip():
        print("SARVAM_API_KEY is missing from the project .env.")
        return 1

    voice = SarvamVoiceService(
        settings.sarvam_api_key,
        settings.sarvam_base_url,
        settings.sarvam_stt_model,
        settings.sarvam_tts_model,
        settings.sarvam_tts_speaker,
        settings.voice_timeout_seconds,
        MockLanguageService(),
    )
    try:
        audio = voice.synthesize(_CHECK_TEXT, Language.HI)
    except ExternalServiceError:
        print("TTS failed; verify the Sarvam key, model settings, and network.")
        return 1

    print("TTS OK")
    try:
        transcript = voice.transcribe(
            base64.b64decode(audio.data_base64, validate=True),
            "sarvam-check.wav",
            audio.content_type,
        )
    except ExternalServiceError:
        print("STT failed; verify the Sarvam key, model settings, and network.")
        return 1

    print("STT OK")
    print(f"transcript: {transcript.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
