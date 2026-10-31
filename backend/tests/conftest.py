from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.container import build_container
from app.core.clock import FixedClock
from app.main import create_app

SVC = {"X-Api-Key": "svc-test-key"}
OP = {"X-Operator-Id": "op1", "X-Operator-Key": "op-test-key"}


def make_settings(**kw) -> Settings:
    base = dict(app_env="test", database_url="sqlite://", service_api_key="svc-test-key",
                operator_api_keys={"op1": "op-test-key"})
    return Settings(_env_file=None, **{**base, **kw})


@pytest.fixture
def clock():
    return FixedClock(datetime(2026, 10, 31, 9, 0, tzinfo=UTC))


@pytest.fixture
def container(clock):
    c = build_container(make_settings(), clock=clock)
    c.db.create_schema()
    return c


@pytest.fixture
def client(container):
    with TestClient(create_app(container.settings, container)) as tc:
        yield tc


def chat(client, merchant_id: str, message: str, session_id: str | None = None):
    body = {"merchant_id": merchant_id, "message": message}
    if session_id:
        body["session_id"] = session_id
    return client.post("/v1/chat", json=body, headers=SVC)
