"""Safety-first hybrid planner: rules for safety-critical intents, then LLM, then rules fallback."""
from __future__ import annotations

from app.modules.planner.base import Planner
from app.modules.planner.rules import RuleBasedPlanner, _SAFETY_INTENTS
from app.schemas.domain import MerchantSummary, Plan, ToolDescriptor


class SafetyFirstPlanner:
    name = "hybrid"

    def __init__(self, primary: Planner, rules: RuleBasedPlanner) -> None:
        self._primary = primary
        self._rules = rules

    def plan(self, message, language, merchant, tools) -> Plan:
        rule_plan = self._rules.plan(message, language, merchant, tools)
        if rule_plan.intent in _SAFETY_INTENTS:
            rule_plan.source = "rules(safety)"
            return rule_plan
        try:
            plan = self._primary.plan(message, language, merchant, tools)
            if plan.intent is not None and getattr(plan.intent, "value", "") != "unknown" and plan.steps:
                return plan
        except Exception:
            pass
        rule_plan.source = "rules(fallback)"
        return rule_plan
