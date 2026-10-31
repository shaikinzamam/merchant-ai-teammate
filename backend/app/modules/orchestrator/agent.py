"""AgentService: Understand -> Decide -> Act -> Collaborate -> Grow.

It depends on the gateway, never on tools. The planner's output is only ever a *proposal*."""
from __future__ import annotations

import logging

from app.modules.audit.service import AuditService
from app.modules.growth.service import GrowthService
from app.modules.language.service import LanguageService
from app.modules.orchestrator.sessions import SessionService
from app.modules.planner.base import Planner
from app.modules.tools.gateway import ToolGateway
from app.modules.tools.registry import ToolRegistry
from app.schemas.api import ActionSummary, ChatRequest, ChatResponse
from app.schemas.domain import (
    ActionContext, Actor, Intent, Language, MerchantSummary, Plan, PlannedStep,
    ProposedAction, ToolOutcome, ToolStatus,
)

log = logging.getLogger(__name__)


class AgentService:
    def __init__(
        self, language: LanguageService, planner: Planner, gateway: ToolGateway,
        registry: ToolRegistry, growth: GrowthService, sessions: SessionService,
        audit: AuditService, max_steps: int,
    ) -> None:
        self._lang, self._planner, self._gateway = language, planner, gateway
        self._registry, self._growth, self._sessions = registry, growth, sessions
        self._audit, self._max_steps = audit, max_steps

    def handle(self, req: ChatRequest) -> ChatResponse:
        language = self._lang.detect(req.message)
        sid = self._sessions.get_or_create(req.session_id, req.merchant_id, language)
        ctx = ActionContext(session_id=sid, merchant_id=req.merchant_id)
        self._audit.record("chat.received", Actor.MERCHANT.value, session_id=sid,
                           merchant_id=req.merchant_id,
                           payload={"language": language.value, "message": req.message})

        # 1. UNDERSTAND: merchant context (through the gateway like every other tool call)
        ctx_out = self._call(ctx, "get_merchant_context", {}, Actor.SYSTEM)
        if ctx_out.status is not ToolStatus.EXECUTED or ctx_out.result is None:
            return self._respond(sid, language, Intent.UNKNOWN, [ctx_out], "none",
                                 self._lang.render("tool_failed", language))
        context = ctx_out.result
        merchant = MerchantSummary(
            preferred_language=context["preferred_language"], has_soundbox=context["has_soundbox"],
            has_edc=context["has_edc"], kyc_status=context["kyc_status"])

        # 2. DECIDE: planner proposes (untrusted)
        plan = self._safe_plan(req.message, language, merchant)
        self._audit.record("plan.proposed", Actor.PLANNER.value, session_id=sid,
                           merchant_id=req.merchant_id,
                           payload={"intent": plan.intent.value, "source": plan.source,
                                    "steps": [s.model_dump() for s in plan.steps]})

        # 3. ACT: every step through the gateway
        outcomes = [self._call(ctx, s.tool, s.params, Actor.PLANNER, s.rationale)
                    for s in plan.steps[: self._max_steps]]

        # 5. GROW: only if nothing risky/failed happened; lead still needs Tier-2 approval
        lead_step = None
        if outcomes and all(o.status is ToolStatus.EXECUTED for o in outcomes):
            lead_step = self._growth.propose(plan.intent, context)
        if lead_step:
            outcomes.append(self._call(ctx, lead_step.tool, lead_step.params, Actor.GROWTH,
                                       lead_step.rationale))

        reply = self._compose(language, plan, outcomes, lead_step)
        return self._respond(sid, language, plan.intent, outcomes, plan.source, reply)

    # ------------------------------------------------------------------------------------
    def _call(self, ctx, tool, params, actor, rationale="") -> ToolOutcome:
        return self._gateway.execute(
            ProposedAction(tool=tool, params=params, proposed_by=actor, rationale=rationale), ctx)

    def _safe_plan(self, message, language, merchant) -> Plan:
        try:
            return self._planner.plan(message, language, merchant,
                                      self._registry.planner_descriptors())
        except Exception:
            log.exception("planner failed")
            return Plan(intent=Intent.UNKNOWN, source="error")

    def _compose(self, lang: Language, plan: Plan, outcomes: list[ToolOutcome],
                 lead_step: PlannedStep | None) -> str:
        r = self._lang.render
        if plan.clarification:
            return r(plan.clarification, lang)
        primary = [o for o in outcomes if o.tool != "create_crm_lead"]
        if not primary:
            return r("unknown_intent", lang)
        if any(o.status is ToolStatus.ESCALATED for o in primary):
            return r("escalated", lang)
        if any(o.status is ToolStatus.DENIED for o in primary):
            return r("denied", lang)
        if any(o.status is ToolStatus.FAILED for o in primary):
            return r("tool_failed", lang)
        if any(o.status is ToolStatus.PENDING_APPROVAL for o in primary):
            return r("approval_pending", lang)
        o = primary[0]
        res = o.result or {}
        if o.tool == "check_settlement_status":
            key = "settlement_delayed" if res.get("status") == "DELAYED" else "settlement_settled"
            text = r(key, lang, date=res.get("date"), expected_by=res.get("expected_by"))
        elif o.tool == "reissue_qr":
            text = r("qr_reissue_done", lang, request_id=res.get("request_id"))
        elif o.tool == "soundbox_diagnostics":
            text = r("soundbox_status", lang, status=res.get("status"))
        elif o.tool == "lookup_faq":
            text = str(res.get("answer", ""))  # English only until the language layer is real
        else:
            text = r("unknown_intent", lang)
        if lead_step:  # no promise made: the lead awaits human approval
            product = str(lead_step.params["product"]).title()
            text += " " + r("growth_hint", lang, product=product)
        return text

    def _respond(self, sid, language, intent, outcomes, planner, reply) -> ChatResponse:
        self._audit.record("chat.replied", Actor.SYSTEM.value, session_id=sid,
                           payload={"intent": intent.value, "reply": reply})
        return ChatResponse(
            session_id=sid, language=language, intent=intent, reply=reply, planner=planner,
            actions=[ActionSummary.from_outcome(o) for o in outcomes
                     if o.tool != "get_merchant_context"])
