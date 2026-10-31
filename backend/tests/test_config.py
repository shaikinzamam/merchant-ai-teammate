from pathlib import Path

import pytest
from pydantic import ValidationError

from app.container import build_container
from app.core.errors import ConfigurationError
from tests.conftest import make_settings


def test_real_tool_backend_refuses_to_start():
    with pytest.raises(ConfigurationError, match="not implemented"):
        build_container(make_settings(tool_backend="real"))


def test_llm_planner_requires_key():
    with pytest.raises(ValidationError):
        make_settings(planner_backend="llm")


def test_voice_is_disabled_by_default_and_sarvam_requires_a_key():
    settings = make_settings()
    assert settings.voice_backend == "off"
    assert settings.sarvam_api_key is None
    with pytest.raises(ValidationError, match="VOICE_BACKEND=sarvam requires SARVAM_API_KEY"):
        make_settings(voice_backend="sarvam")


def test_production_rejects_weak_keys_and_default_db():
    with pytest.raises(ValidationError):
        make_settings(app_env="production", database_url="postgresql+psycopg://a:b@h/db")


def test_service_key_is_required_and_secret():
    from app.config import Settings
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
    assert "svc-test-key" not in repr(make_settings())


def test_default_env_file_is_resolved_from_project_root():
    from app.config import PROJECT_ENV_FILE

    assert PROJECT_ENV_FILE == Path(__file__).resolve().parents[2] / ".env"
    assert PROJECT_ENV_FILE.is_absolute()


def test_local_demo_credentials_load_from_env_file(tmp_path):
    from app.config import Settings

    env_file = tmp_path / ".env"
    env_file.write_text(
        'SERVICE_API_KEY=local-demo-service-key\n'
        'OPERATOR_API_KEYS={"op-demo":"local-demo-operator-key"}\n'
        'PLANNER_BACKEND=rules\n',
        encoding="utf-8",
    )
    settings = Settings(_env_file=env_file)

    assert settings.service_api_key.get_secret_value() == "local-demo-service-key"
    assert settings.operator_api_keys["op-demo"].get_secret_value() == "local-demo-operator-key"


def test_authentication_credentials_cannot_be_empty_or_unconfigured():
    with pytest.raises(ValidationError, match="OPERATOR_API_KEYS"):
        make_settings(operator_api_keys={})
    with pytest.raises(ValidationError, match="SERVICE_API_KEY"):
        make_settings(service_api_key="")
    with pytest.raises(ValidationError, match="OPERATOR_API_KEYS"):
        make_settings(operator_api_keys={"op1": ""})
