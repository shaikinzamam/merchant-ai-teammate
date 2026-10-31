from __future__ import annotations

import base64
import json

import httpx
import pytest
from pydantic import SecretStr

from app.core.errors import ExternalServiceError
from app.modules.language.service import MockLanguageService
from app.modules.voice.sarvam import SarvamVoiceService
from app.schemas.domain import Language


def make_service(transport):
    return SarvamVoiceService(
        SecretStr("sarvam-test-secret"),
        "https://api.sarvam.ai",
        "saaras:v4",
        "bulbul:v4-flash",
        "shubh_enhi_ads",
        3.5,
        MockLanguageService(),
        transport=transport,
    )


def test_sarvam_uses_documented_stt_and_tts_contract():
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/speech-to-text":
            assert request.headers["api-subscription-key"] == "sarvam-test-secret"
            assert b'name="model"\r\n\r\nsaaras:v4' in request.content
            assert b'name="mode"\r\n\r\ntranscribe' in request.content
            return httpx.Response(
                200, json={"transcript": "ನಮಸ್ಕಾರ", "language_code": "kn-IN"}
            )
        body = json.loads(request.content)
        assert body == {
            "text": "ನಮಸ್ಕಾರ",
            "language_code": "kn-IN",
            "model": "bulbul:v4-flash",
            "speaker": "shubh_enhi_ads",
        }
        return httpx.Response(200, json={"audios": [base64.b64encode(b"wav").decode()]})

    service = make_service(httpx.MockTransport(respond))
    transcript = service.transcribe(b"webm", "recording.webm", "audio/webm")
    audio = service.synthesize(transcript.text, transcript.language)

    assert transcript.language is Language.KN
    assert audio.content_type == "audio/wav"
    assert len(requests) == 2
    assert requests[0].url == "https://api.sarvam.ai/speech-to-text"
    assert requests[1].url == "https://api.sarvam.ai/text-to-speech"


def test_unknown_stt_language_falls_back_to_language_detection():
    service = make_service(
        httpx.MockTransport(
            lambda _: httpx.Response(
                200, json={"transcript": "नमस्ते, मेरा खाता", "language_code": "unsupported"}
            )
        )
    )
    assert service.transcribe(b"audio", "recording.webm", "audio/webm").language is Language.HI


def test_stt_retries_one_server_error_but_not_client_errors():
    attempts = 0

    def server_error_then_success(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            503 if attempts == 1 else 200,
            json={"transcript": "hello", "language_code": "en-IN"},
        )

    service = make_service(httpx.MockTransport(server_error_then_success))
    assert service.transcribe(b"audio", "recording.webm", "audio/webm").text == "hello"
    assert attempts == 2

    attempts = 0

    def client_error(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, json={"error": "sarvam-test-secret"})

    service = make_service(httpx.MockTransport(client_error))
    with pytest.raises(ExternalServiceError) as raised:
        service.transcribe(b"audio", "recording.webm", "audio/webm")
    assert attempts == 1
    assert "sarvam-test-secret" not in str(raised.value)
