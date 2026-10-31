"""initial schema: sessions, audit_events, human_tasks

Revision ID: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("merchant_id", sa.String(32), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_sessions_merchant_id", "sessions", ["merchant_id"])

    op.create_table(
        "audit_events",
        sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ts", TS, nullable=False),
        sa.Column("session_id", sa.String(64)),
        sa.Column("merchant_id", sa.String(32)),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("actor", sa.String(32), nullable=False),
        sa.Column("tool_name", sa.String(64)),
        sa.Column("decision", sa.String(32)),
        sa.Column("tier", sa.Integer),
        sa.Column("risk_score", sa.Integer),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
    )
    for col in ("session_id", "merchant_id", "event_type"):
        op.create_index(f"ix_audit_events_{col}", "audit_events", [col])

    op.create_table(
        "human_tasks",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("merchant_id", sa.String(32), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("params", sa.JSON, nullable=False),
        sa.Column("proposed_by", sa.String(16), nullable=False),
        sa.Column("action_hash", sa.String(64), nullable=False),
        sa.Column("tier", sa.Integer, nullable=False),
        sa.Column("risk_score", sa.Integer, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("brief", sa.JSON, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("expires_at", TS),
        sa.Column("decided_by", sa.String(64)),
        sa.Column("decided_at", TS),
    )
    for col in ("kind", "status", "merchant_id", "session_id"):
        op.create_index(f"ix_human_tasks_{col}", "human_tasks", [col])


def downgrade() -> None:
    op.drop_table("human_tasks")
    op.drop_table("audit_events")
    op.drop_table("sessions")
