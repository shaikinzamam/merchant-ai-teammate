"""Typed, validated configuration.

Keeps the project's existing env names (APP_ENV, DATABASE_URL, GROQ_API_KEY, GROQ_MODEL) and adds
governance settings. Secrets are SecretStr; service/operator keys have NO defaults (fail fast).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://merchant:merchant@localhost:5432/merchant_ai"

    # Secrets: required, no defaults.
    service_api_key: SecretStr  # merchant-facing /v1/chat
    operator_api_keys: dict[str, SecretStr]  # JSON {"op-1":"key"}

    # Integrations. Only "mock" exists; "real" fails at startup by design.
    tool_backend: Literal["mock", "real"] = "mock"
    planner_backend: Literal["rules", "llm"] = "rules"
    groq_api_key: SecretStr | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: float = 15.0

    # Optional push-to-talk voice adapter.
    voice_backend: Literal["off", "sarvam"] = "off"
    sarvam_api_key: SecretStr | None = None
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_stt_model: str = "saaras:v4"
    sarvam_tts_model: str = "bulbul:v4-flash"
    sarvam_tts_speaker: str = "shubh_enhi_ads"
    voice_max_audio_bytes: int = Field(5_000_000, ge=1)
    voice_timeout_seconds: float = Field(30.0, gt=0)

    # Governance knobs
    approval_ttl_minutes: int = Field(30, ge=1, le=1440)
    max_tool_calls_per_session: int = Field(30, ge=1)
    max_steps_per_plan: int = Field(5, ge=1, le=10)

    # Growth thresholds: PLACEHOLDERS for the prototype, not validated business rules.
    growth_soundbox_min_daily_volume_inr: int = 25_000
    growth_edc_min_daily_volume_inr: int = 100_000

    @model_validator(mode="after")
    def _validate(self) -> Settings:
        if not self.service_api_key.get_secret_value().strip():
            raise ValueError("SERVICE_API_KEY must not be empty")
        if not self.operator_api_keys:
            raise ValueError("OPERATOR_API_KEYS must configure at least one operator ID and key")
        if any(not operator_id.strip() or not key.get_secret_value().strip()
               for operator_id, key in self.operator_api_keys.items()):
            raise ValueError("OPERATOR_API_KEYS must not contain blank IDs or keys")
        if self.planner_backend == "llm" and not self.groq_api_key:
            raise ValueError("PLANNER_BACKEND=llm requires GROQ_API_KEY")
        if self.voice_backend == "sarvam" and (
            not self.sarvam_api_key or not self.sarvam_api_key.get_secret_value().strip()
        ):
            raise ValueError("VOICE_BACKEND=sarvam requires SARVAM_API_KEY")
        if self.app_env == "production":
            keys = [self.service_api_key, *self.operator_api_keys.values()]
            if any(len(k.get_secret_value()) < 32 for k in keys):
                raise ValueError("production API keys must be at least 32 characters")
            if self.database_url.startswith("sqlite") or "merchant:merchant@" in self.database_url:
                raise ValueError("production requires a non-default PostgreSQL URL")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # required values come from the environment
