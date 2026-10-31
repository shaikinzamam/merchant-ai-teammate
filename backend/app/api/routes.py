from __future__ import annotations

import time
import logging
from email import policy
from email.parser import BytesParser

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_container, require_operator, require_service
from app.container import Container
from app.core.errors import AppError, ExternalServiceError, NotAvailableError
from app.modules.audit.service import AuditEvent
from app.modules.voice.schemas import SynthesizedAudio
from app.schemas.domain import Actor, Intent, Language
from app.schemas.api import (
    ApprovalResult, ChainVerificationView, ChatRequest, ChatResponse, DecisionRequest,
    VoiceChatResponse, VoiceSpeakRequest, VoiceStatusResponse,
)
from app.schemas.domain import HumanTask, TaskKind, TaskStatus

router = APIRouter()
logger = logging.getLogger(__name__)
_VOICE_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/mpeg3", "audio/x-mpeg-3", "audio/x-mp3",
    "audio/aac", "audio/x-aac", "audio/wav", "audio/x-wav", "audio/wave",
    "audio/aiff", "audio/x-aiff", "audio/ogg", "audio/opus", "audio/flac",
    "audio/x-flac", "audio/mp4", "audio/x-m4a", "audio/amr", "audio/x-ms-wma",
    "audio/webm",
}
_MAX_MULTIPART_OVERHEAD = 64 * 1024


async def _voice_form(request: Request, max_audio_bytes: int) -> tuple[bytes, str, str, str, str | None]:
    request_content_type = request.headers.get("content-type", "")
    if request_content_type.split(";", 1)[0].strip().lower() != "multipart/form-data":
        raise HTTPException(415, "Voice requests must use multipart form data")

    max_request_bytes = max_audio_bytes + _MAX_MULTIPART_OVERHEAD
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_request_bytes:
                raise HTTPException(413, "Audio exceeds the configured size limit")
        except ValueError:
            raise HTTPException(400, "Invalid content length") from None

    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > max_request_bytes:
            raise HTTPException(413, "Audio exceeds the configured size limit")
        body.extend(chunk)

    try:
        headers = (
            f"Content-Type: {request_content_type}\r\nMIME-Version: 1.0\r\n\r\n"
        ).encode("ascii")
        form = BytesParser(policy=policy.default).parsebytes(headers + bytes(body))
    except (UnicodeEncodeError, ValueError):
        raise HTTPException(400, "Invalid multipart form data") from None
    if not form.is_multipart():
        raise HTTPException(400, "Invalid multipart form data")

    fields: dict[str, str] = {}
    audio_part = None
    for part in form.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not isinstance(name, str) or name in fields or (name == "audio" and audio_part):
            raise HTTPException(400, "Invalid or duplicate form field")
        if name == "audio":
            if not part.get_filename():
                raise HTTPException(400, "Audio file is required")
            audio_part = part
        elif name in {"merchant_id", "session_id"} and not part.get_filename():
            payload = part.get_payload(decode=True)
            try:
                fields[name] = (payload or b"").decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(400, "Form fields must use UTF-8") from None
        else:
            raise HTTPException(400, "Unexpected form field")

    if audio_part is None:
        raise HTTPException(400, "Audio file is required")
    audio = audio_part.get_payload(decode=True) or b""
    if len(audio) > max_audio_bytes:
        raise HTTPException(413, "Audio exceeds the configured size limit")
    if not audio:
        raise HTTPException(400, "Audio file is empty")
    audio_content_type = audio_part.get_content_type().lower()
    if audio_content_type not in _VOICE_AUDIO_TYPES:
        raise HTTPException(415, "Audio format is not supported")
    if "merchant_id" not in fields:
        raise HTTPException(400, "merchant_id is required")
    return audio, audio_part.get_filename() or "recording", audio_content_type, fields[
        "merchant_id"
    ], fields.get("session_id") or None


@router.get("/", tags=["health"])
def root() -> dict[str, str]:
    return {"message": "Merchant AI Teammate API", "docs": "/docs"}


@router.get("/health", tags=["health"])
def health(c: Container = Depends(get_container)) -> dict[str, str | dict[str, bool]]:
    try:
        with c.db.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise AppError("database unavailable") from exc  # mapped to 503 in main
    return {"status": "ok", "environment": c.settings.app_env, "database": "connected",
            "tools": "SIMULATED" if c.integration.is_simulated else "REAL",
            "configuration": {
                "service_api_key_configured": bool(
                    c.settings.service_api_key.get_secret_value().strip()
                )
            }}


@router.post("/v1/chat", response_model=ChatResponse, tags=["agent"],
             dependencies=[Depends(require_service)])
def chat(body: ChatRequest, c: Container = Depends(get_container)) -> ChatResponse:
    return c.agent.handle(body)


@router.get(
    "/v1/voice/status", response_model=VoiceStatusResponse, tags=["agent"],
    dependencies=[Depends(require_service)],
)
def voice_status(c: Container = Depends(get_container)) -> VoiceStatusResponse:
    enabled = c.settings.voice_backend == "sarvam"
    return VoiceStatusResponse(
        enabled=enabled,
        provider="sarvam" if enabled else "off",
        stt_model=c.settings.sarvam_stt_model,
        tts_model=c.settings.sarvam_tts_model,
    )


@router.post(
    "/v1/voice/chat", response_model=VoiceChatResponse, tags=["agent"],
    dependencies=[Depends(require_service)],
)
async def voice_chat(request: Request, c: Container = Depends(get_container)) -> VoiceChatResponse:
    if c.settings.voice_backend == "off":
        raise NotAvailableError("Voice is not enabled")

    audio, filename, content_type, merchant_id, session_id = await _voice_form(
        request, c.settings.voice_max_audio_bytes
    )
    try:
        ChatRequest(merchant_id=merchant_id, message="voice input", session_id=session_id)
    except ValueError:
        raise HTTPException(422, "Invalid merchant_id or session_id") from None

    started = time.perf_counter()
    transcript = await run_in_threadpool(c.voice.transcribe, audio, filename, content_type)
    duration_ms = round((time.perf_counter() - started) * 1000)
    text = transcript.text.strip()
    if not text:
        reply = c.language.render("voice_empty", transcript.language)
        c.audit.record(
            "voice.transcribed", Actor.MERCHANT.value, session_id=session_id,
            merchant_id=merchant_id,
            payload={
                "language": transcript.language.value,
                "audio_bytes": len(audio),
                "duration_ms": duration_ms,
            },
        )
        return VoiceChatResponse(
            session_id=session_id or "", language=transcript.language, intent=Intent.UNKNOWN,
            reply=reply, actions=[], planner="none", transcript="",
            detected_language=transcript.language, audio=None,
        )

    chat_response = await run_in_threadpool(
        c.agent.handle, ChatRequest(merchant_id=merchant_id, message=text, session_id=session_id)
    )
    c.audit.record(
        "voice.transcribed", Actor.MERCHANT.value, session_id=chat_response.session_id,
        merchant_id=merchant_id,
        payload={
            "language": transcript.language.value,
            "audio_bytes": len(audio),
            "duration_ms": duration_ms,
        },
    )
    audio_response = None
    reply_language = c.language.detect(chat_response.reply)
    try:
        audio_response = await run_in_threadpool(
            c.voice.synthesize, chat_response.reply, reply_language
        )
    except ExternalServiceError as exc:
        logger.warning("TTS failed for reply: %s", exc)
    return VoiceChatResponse(
        **chat_response.model_dump(), transcript=text,
        detected_language=transcript.language, audio=audio_response,
    )


@router.get("/v1/operator/whoami", tags=["operator"])
def operator_whoami(operator_id: str = Depends(require_operator)) -> dict[str, str]:
    """Validate an operator credential without disclosing any configured credentials."""
    return {"operator_id": operator_id}


@router.get("/v1/approvals", response_model=list[HumanTask], tags=["operator"])
def list_approvals(status: TaskStatus | None = TaskStatus.PENDING,
                   _op: str = Depends(require_operator), c: Container = Depends(get_container)):
    return c.tasks.list(TaskKind.APPROVAL, status)


@router.post("/v1/approvals/{task_id}/approve", response_model=ApprovalResult, tags=["operator"])
def approve(task_id: str, body: DecisionRequest | None = None,
            op: str = Depends(require_operator), c: Container = Depends(get_container)):
    task, outcome = c.approvals.approve(task_id, op, body.note if body else None)
    return ApprovalResult(task=task, outcome=outcome)


@router.post("/v1/approvals/{task_id}/reject", response_model=ApprovalResult, tags=["operator"])
def reject(task_id: str, body: DecisionRequest | None = None,
           op: str = Depends(require_operator), c: Container = Depends(get_container)):
    return ApprovalResult(task=c.approvals.reject(task_id, op, body.note if body else None))


@router.get("/v1/escalations", response_model=list[HumanTask], tags=["operator"])
def list_escalations(status: TaskStatus | None = TaskStatus.OPEN,
                     _op: str = Depends(require_operator), c: Container = Depends(get_container)):
    return c.tasks.list(TaskKind.ESCALATION, status)


@router.post("/v1/escalations/{task_id}/close", response_model=HumanTask, tags=["operator"])
def close_escalation(task_id: str, body: DecisionRequest | None = None,
                     op: str = Depends(require_operator), c: Container = Depends(get_container)):
    return c.tasks.close_escalation(task_id, op, body.note if body else None)


@router.get("/v1/audit", response_model=list[AuditEvent], tags=["operator"])
def audit_events(session_id: str | None = None, limit: int = Query(100, ge=1, le=500),
                 _op: str = Depends(require_operator), c: Container = Depends(get_container)):
    return c.audit.list_events(session_id, limit)


@router.get("/v1/audit/verify", response_model=ChainVerificationView, tags=["operator"])
def audit_verify(_op: str = Depends(require_operator), c: Container = Depends(get_container)):
    return c.audit.verify_chain()

@router.post("/v1/voice/speak", response_model=SynthesizedAudio, tags=["agent"], dependencies=[Depends(require_service)])
def voice_speak(body: VoiceSpeakRequest, c: Container = Depends(get_container)) -> SynthesizedAudio:
    return c.voice.synthesize(body.text, body.language)


