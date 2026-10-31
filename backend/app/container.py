"""Composition root: the only place concrete implementations are chosen and wired together.
Tests override pieces via keyword arguments (planner / integration / clock)."""
from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.core.clock import Clock, SystemClock
from app.core.errors import ConfigurationError, NotAvailableError
from app.database.session import Database
from app.integrations.mock_paytm.integration import MockPaytmIntegration
from app.integrations.paytm_real.integration import RealPaytmIntegration
from app.modules.approvals.service import HumanTaskService
from app.modules.approvals.workflow import ApprovalWorkflow
from app.modules.audit.service import AuditService
from app.modules.growth.service import GrowthService
from app.modules.language.service import LanguageService, MockLanguageService
from app.modules.orchestrator.agent import AgentService
from app.modules.orchestrator.sessions import SessionService
from app.modules.planner.base import Planner
from app.modules.planner.llm import FallbackPlanner, GroqLLMClient, LLMPlanner
from app.modules.planner.rules import RuleBasedPlanner
from app.modules.planner.hybrid import SafetyFirstPlanner
from app.modules.policy.engine import PolicyEngine
from app.modules.policy.matrix import POLICY_MATRIX
from app.modules.policy.risk import RiskEngine
from app.modules.tools.base import ToolIntegration
from app.modules.tools.gateway import ToolGateway
from app.modules.tools.registry import ToolRegistry
from app.modules.voice.disabled import DisabledVoiceService
from app.modules.voice.sarvam import SarvamVoiceService
from app.modules.voice.service import VoiceService


@dataclass
class Container:
    settings: Settings
    db: Database
    clock: Clock
    audit: AuditService
    registry: ToolRegistry
    integration: ToolIntegration
    gateway: ToolGateway
    tasks: HumanTaskService
    approvals: ApprovalWorkflow
    language: LanguageService
    planner: Planner
    agent: AgentService
    voice: VoiceService


def _build_integration(settings: Settings, clock: Clock) -> ToolIntegration:
    if settings.tool_backend == "mock":
        return MockPaytmIntegration(clock)
    try:
        return RealPaytmIntegration()
    except NotAvailableError as exc:
        raise ConfigurationError(str(exc)) from exc


def _build_planner(settings: Settings) -> Planner:
    rules = RuleBasedPlanner()
    if settings.planner_backend == "rules":
        return rules
    assert settings.groq_api_key is not None  # guaranteed by Settings validation
    client = GroqLLMClient(settings.groq_api_key.get_secret_value(), settings.groq_model,
                           settings.llm_timeout_seconds)
    llm = FallbackPlanner(LLMPlanner(client, settings.max_steps_per_plan), rules)
    return SafetyFirstPlanner(llm, rules)


def build_container(
    settings: Settings, *, planner: Planner | None = None,
    integration: ToolIntegration | None = None, clock: Clock | None = None,
    voice_service: VoiceService | None = None,
) -> Container:
    clock = clock or SystemClock()
    db = Database(settings.database_url)
    audit = AuditService(db, clock)
    integration = integration or _build_integration(settings, clock)
    registry = ToolRegistry(integration.tool_specs())

    missing = registry.names() ^ set(POLICY_MATRIX)  # every tool needs a policy and vice versa
    if missing:
        raise ConfigurationError(f"tools and policy matrix out of sync: {sorted(missing)}")

    policy = PolicyEngine(POLICY_MATRIX, registry.params_model, RiskEngine(),
                          settings.max_tool_calls_per_session)
    tasks = HumanTaskService(db, clock, audit, settings.approval_ttl_minutes)
    gateway = ToolGateway(registry, policy, integration.risk_signals(), tasks, audit)
    language = MockLanguageService()
    if voice_service is None:
        if settings.voice_backend == "sarvam":
            assert settings.sarvam_api_key is not None
            voice_service = SarvamVoiceService(
                settings.sarvam_api_key, settings.sarvam_base_url,
                settings.sarvam_stt_model, settings.sarvam_tts_model,
                settings.sarvam_tts_speaker, settings.voice_timeout_seconds, language,
            )
        else:
            voice_service = DisabledVoiceService()
    planner = planner or _build_planner(settings)
    growth = GrowthService(settings.growth_soundbox_min_daily_volume_inr,
                           settings.growth_edc_min_daily_volume_inr)
    agent = AgentService(language, planner, gateway, registry, growth,
                         SessionService(db, clock), audit, settings.max_steps_per_plan)
    return Container(settings, db, clock, audit, registry, integration, gateway, tasks,
                     ApprovalWorkflow(tasks, gateway), language, planner, agent, voice_service)
