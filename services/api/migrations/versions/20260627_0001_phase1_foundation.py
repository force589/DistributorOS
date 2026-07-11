"""Create the Phase 1 identity and tenancy foundation.

Revision ID: 20260627_0001
Revises: None
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260627_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "businesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(trim(business_name)) > 0",
            name=op.f("ck_businesses_business_name_not_blank"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_businesses")),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_table(
        "memberships",
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('owner')", name=op.f("ck_memberships_supported_role")),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            name=op.f("fk_memberships_business_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("business_id", "user_id", name=op.f("pk_memberships")),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("refresh_transport", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "refresh_transport IN ('native', 'cookie')",
            name=op.f("ck_auth_sessions_refresh_transport"),
        ),
        sa.ForeignKeyConstraint(
            ["business_id", "user_id"],
            ["memberships.business_id", "memberships.user_id"],
            name=op.f("fk_auth_sessions_business_id_memberships"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)

    tenant_id = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    user_id = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"
    maintenance = "current_setting('app.internal_maintenance', true) = 'true'"

    for table in ("businesses", "memberships", "auth_sessions"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')

    op.execute(
        f"""
        CREATE POLICY businesses_insert ON businesses
        FOR INSERT
        WITH CHECK ({maintenance} OR id = {tenant_id})
        """
    )
    op.execute(  # noqa: S608 -- SQL fragments below are constants, never user input.
        f"""
        CREATE POLICY businesses_select ON businesses
        FOR SELECT
        USING (
            {maintenance}
            OR (
                id = {tenant_id}
                AND EXISTS (
                    SELECT 1 FROM memberships
                    WHERE memberships.business_id = businesses.id
                    AND memberships.user_id = {user_id}
                )
            )
        )
        """
    )
    op.execute(
        f"""
        CREATE POLICY memberships_select ON memberships
        FOR SELECT
        USING ({maintenance} OR user_id = {user_id})
        """
    )
    op.execute(
        f"""
        CREATE POLICY memberships_insert ON memberships
        FOR INSERT
        WITH CHECK ({maintenance} OR (user_id = {user_id} AND business_id = {tenant_id}))
        """
    )
    op.execute(
        f"""
        CREATE POLICY auth_sessions_user_access ON auth_sessions
        FOR ALL
        USING ({maintenance} OR user_id = {user_id})
        WITH CHECK ({maintenance} OR user_id = {user_id})
        """
    )

def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS businesses_select ON businesses")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("memberships")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_table("businesses")
