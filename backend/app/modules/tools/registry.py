from __future__ import annotations

from pydantic import BaseModel

from app.core.errors import ConfigurationError
from app.modules.tools.base import ToolSpec
from app.modules.tools.schemas import EscalateParams
from app.schemas.domain import ToolDescriptor

ESCALATE_SPEC = ToolSpec(
    name="escalate_to_human",
    description="Escalate the case to a human operator (fraud, repeated KYC failure, chargeback, churn).",
    params_model=EscalateParams,
    handler=None,
)

# Tools the planner must never be shown (orchestrator-internal).
_INTERNAL = {"get_merchant_context"}


class ToolRegistry:
    def __init__(self, specs: list[ToolSpec]) -> None:
        self._specs: dict[str, ToolSpec] = {}
        for spec in [*specs, ESCALATE_SPEC]:
            if spec.name in self._specs:
                raise ConfigurationError(f"duplicate tool: {spec.name}")
            self._specs[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def params_model(self, name: str) -> type[BaseModel] | None:
        spec = self._specs.get(name)
        return spec.params_model if spec else None

    def names(self) -> set[str]:
        return set(self._specs)

    def planner_descriptors(self) -> list[ToolDescriptor]:
        return [
            ToolDescriptor(
                name=s.name, description=s.description,
                params_schema=s.params_model.model_json_schema(),
            )
            for s in self._specs.values()
            if s.name not in _INTERNAL
        ]
