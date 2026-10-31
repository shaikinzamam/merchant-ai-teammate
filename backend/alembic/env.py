from __future__ import annotations

import os
from pathlib import Path

from alembic import context
from dotenv import dotenv_values
from sqlalchemy import create_engine

from app.database.models import Base

target_metadata = Base.metadata
DEFAULT_URL = "postgresql+psycopg://merchant:merchant@localhost:5432/merchant_ai"


def _url() -> str:
    """DATABASE_URL from the process env, else ../.env / .env (same lookup as app.config).
    Only the DB URL is needed, so API keys are not required to run migrations."""
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    backend = Path(__file__).resolve().parents[1]
    for env_file in (backend.parent / ".env", backend / ".env"):
        value = dotenv_values(env_file).get("DATABASE_URL") if env_file.exists() else None
        if value:
            return value
    return DEFAULT_URL


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
