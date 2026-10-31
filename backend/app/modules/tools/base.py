"""Tool contracts. Integrations (mock or real) implement ToolIntegration; nothing else
in the system can reach a tool handler except the ToolGateway."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from app.schemas.domain import RiskSignals

Handler = Callable[[str, Any], dict[str, Any]]  # (merchant_id, validated_params) -> result


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    params_model: type[BaseModel]
    handler: Handler | None  # None => handled by the gateway itself (e.g. escalate_to_human)


class RiskSignalProvider(Protocol):
    """System-of-record facts used by the risk engine (independent of LLM / caller input)."""

    def signals_for(self, merchant_id: str, txn_id: str | None) -> RiskSignals: ...


class ToolIntegration(Protocol):
    """Implemented by app.integrations.mock_paytm (today) and a future real Paytm adapter."""

    name: str
    is_simulated: bool

    def tool_specs(self) -> list[ToolSpec]: ...
    def risk_signals(self) -> RiskSignalProvider: ...
