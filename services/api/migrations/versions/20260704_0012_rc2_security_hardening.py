"""Add RC-2 authentication, abuse-protection, and outbox infrastructure.

Revision ID: 20260704_0012
Revises: 20260703_0011
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260704_0012"
down_revision: str | None = "20260703_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "auth_sessions",
        sa.Column("previous_refresh_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "auth_sessions",
        sa.Column("previous_refresh_valid_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name=op.f("fk_password_reset_tokens_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_password_reset_tokens_user_id"),
        "password_reset_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "request_rate_limits",
        sa.Column("scope", sa.String(length=80), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint(
            "scope", "key_hash", "window_started_at", name=op.f("pk_request_rate_limits")
        ),
    )
    op.create_index(
        op.f("ix_request_rate_limits_expires_at"),
        "request_rate_limits",
        ["expires_at"],
        unique=False,
    )
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
    )
    op.create_index(op.f("ix_outbox_events_event_type"), "outbox_events", ["event_type"])
    op.create_index(op.f("ix_outbox_events_available_at"), "outbox_events", ["available_at"])

    op.execute("GRANT UPDATE ON users TO distributoros_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON password_reset_tokens TO distributoros_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON request_rate_limits TO distributoros_app")
    op.execute("GRANT SELECT, INSERT ON outbox_events TO distributoros_app")


def downgrade() -> None:
    op.drop_index(op.f("ix_outbox_events_available_at"), table_name="outbox_events")
    op.drop_index(op.f("ix_outbox_events_event_type"), table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index(op.f("ix_request_rate_limits_expires_at"), table_name="request_rate_limits")
    op.drop_table("request_rate_limits")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("auth_sessions", "previous_refresh_valid_until")
    op.drop_column("auth_sessions", "previous_refresh_token_hash")
