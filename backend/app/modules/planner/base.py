from __future__ import annotations

from typing import Protocol

from app.schemas.domain import Language, MerchantSummary, Plan, ToolDescriptor


class Planner(Protocol):
    name: str

    def plan(
        self, message: str, language: Language, merchant: MerchantSummary,
        tools: list[ToolDescriptor],
    ) -> Plan: ...
