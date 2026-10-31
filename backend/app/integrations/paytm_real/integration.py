"""PLACEHOLDER for a future real Paytm integration.

No production Paytm API is accessed by this project. This class exists only so the seam is explicit:
a real adapter would implement ToolIntegration here. Constructing it fails on purpose.
"""
from __future__ import annotations

from app.core.errors import NotAvailableError
from app.modules.tools.base import RiskSignalProvider, ToolSpec


class RealPaytmIntegration:
    name = "paytm_real"
    is_simulated = False

    def __init__(self) -> None:
        raise NotAvailableError(
            "Real Paytm integration is not implemented. This prototype uses simulated tools only."
        )

    def tool_specs(self) -> list[ToolSpec]:  # pragma: no cover
        raise NotImplementedError

    def risk_signals(self) -> RiskSignalProvider:  # pragma: no cover
        raise NotImplementedError
