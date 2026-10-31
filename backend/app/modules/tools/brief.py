"""Synthesises the case brief handed to a human operator on escalation (template-based)."""
from __future__ import annotations

from typing import Any

from app.schemas.domain import PolicyDecision, ProposedAction


def build_brief(proposed: ProposedAction, decision: PolicyDecision, events: list[Any]) -> dict:
    return {
        "proposed_action": {"tool": proposed.tool, "params": decision.params,
                            "proposed_by": proposed.proposed_by.value,
                            "rationale": proposed.rationale},
        "why_escalated": decision.reasons,
        "risk_score": decision.risk.score,
        "risk_signals": decision.risk.signals,
        "recent_session_events": [
            {"seq": e.seq, "event": e.event_type, "tool": e.tool_name, "decision": e.decision}
            for e in events[-15:]
        ],
    }
