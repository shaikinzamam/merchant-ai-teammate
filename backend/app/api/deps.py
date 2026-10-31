"""Auth dependencies (constant-time key comparison)."""
from __future__ import annotations

import secrets

from fastapi import Depends, Header, Request

from app.container import Container
from app.core.errors import Unauthorized


def get_container(request: Request) -> Container:
    return request.app.state.container


def _eq(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode(), b.encode())


def require_service(
    c: Container = Depends(get_container),
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
) -> None:
    if not x_api_key or not _eq(x_api_key, c.settings.service_api_key.get_secret_value()):
        raise Unauthorized("X-Api-Key is required and must match SERVICE_API_KEY configured in backend .env")


def require_operator(
    c: Container = Depends(get_container),
    x_operator_id: str | None = Header(None, alias="X-Operator-Id"),
    x_operator_key: str | None = Header(None, alias="X-Operator-Key"),
) -> str:
    expected = c.settings.operator_api_keys.get(x_operator_id or "")
    candidate = x_operator_key or ""
    ok = _eq(candidate, expected.get_secret_value() if expected else "\0")  # constant-ish time
    if not (x_operator_id and x_operator_key and expected and ok):
        raise Unauthorized(
            "X-Operator-Id and X-Operator-Key must match an entry in OPERATOR_API_KEYS configured in backend .env"
        )
    return x_operator_id
