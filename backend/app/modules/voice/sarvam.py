"""Sarvam REST speech adapter. Provider errors never include response details or credentials."""
from __future__ import annotations

import base64
from typing import Any

import httpx
from pydantic import SecretStr

from app.core.errors import ExternalServiceError
from app.modules.language.service import LanguageService
from app.modules.voice.schemas import SynthesizedAudio, Transcript
from app.schemas.domain import Language

_LANGUAGE_CODES = {
    "en-IN": Language.EN,
    "hi-IN": Language.HI,
    "te-IN": Language.TE,
    "kn-IN": Language.KN,
}
_SARVAM_CODES = {language: code for code, language in _LANGUAGE_CODES.items()}
_GENERIC_ERROR = "Speech service request failed"


class SarvamVoiceService:
    def __init__(
        self,
        api_key: SecretStr,
        base_url: str,
        stt_model: str,
        tts_model: str,
        tts_speaker: str,
        timeout_seconds: float,
        language: LanguageService,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key.get_secret_value()
        self._base_url = base_url.rstrip("/")
        self._stt_model = stt_model
        self._tts_model = tts_model
        self._tts_speaker = tts_speaker
        self._timeout_seconds = timeout_seconds
        self._language = language
        self._transport = transport

    def transcribe(self, audio: bytes, filename: str, content_type: str) -> Transcript:
        try:
            response = self._post(
                "speech-to-text",
                data={"model": self._stt_model, "mode": "transcribe"},
                files={"file": (filename, audio, content_type)},
            )
            result = response.json()
            text = result.get("transcript")
            if not isinstance(text, str):
                raise ValueError("Invalid transcription response")
            detected_code = result.get("language_code")
            detected_language = (
                _LANGUAGE_CODES.get(detected_code) if isinstance(detected_code, str) else None
            )
            return Transcript(
                text=text,
                language=detected_language or self._language.detect(text),
            )
        except ExternalServiceError:
            raise
        except Exception:
            raise ExternalServiceError(_GENERIC_ERROR) from None

    def synthesize(self, text: str, language: Language) -> SynthesizedAudio:
        try:
            response = self._post(
                "text-to-speech",
                json_body={
                    "text": text,
                    "language_code": _SARVAM_CODES[language],
                    "model": self._tts_model,
                    "speaker": self._tts_speaker,
                },
            )
            result = response.json()
            audios = result.get("audios")
            if not isinstance(audios, list) or not audios or not all(
                isinstance(item, str) for item in audios
            ):
                raise ValueError("Invalid synthesis response")
            encoded = "".join(audios)
            if not encoded:
                raise ValueError("Empty synthesis response")
            base64.b64decode(encoded, validate=True)
            return SynthesizedAudio(content_type="audio/wav", data_base64=encoded)
        except ExternalServiceError:
            raise
        except Exception:
            raise ExternalServiceError(_GENERIC_ERROR) from None

    def _post(
        self,
        endpoint: str,
        *,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        for attempt in range(2):
            try:
                with httpx.Client(
                    timeout=self._timeout_seconds, transport=self._transport
                ) as client:
                    response = client.post(
                        f"{self._base_url}/{endpoint}",
                        headers={"api-subscription-key": self._api_key},
                        data=data,
                        files=files,
                        json=json_body,
                    )
            except httpx.HTTPError:
                raise ExternalServiceError(_GENERIC_ERROR) from None
            if response.status_code >= 500 and attempt == 0:
                continue
            if response.is_error:
                raise ExternalServiceError(_GENERIC_ERROR) from None
            return response
        raise ExternalServiceError(_GENERIC_ERROR)
