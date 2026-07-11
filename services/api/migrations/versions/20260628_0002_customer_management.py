"""Add Phase 2 customer management.

Revision ID: 20260628_0002
Revises: 20260627_0001
Create Date: 2026-06-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260628_0002"
down_revision: str | None = "20260627_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "customer_code_counters",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_customer_code_counters_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tenant_id", name=op.f("pk_customer_code_counters")),
    )
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("address_line_1", sa.String(length=200), nullable=True),
        sa.Column("address_line_2", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("archived", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "char_length(trim(name)) > 0",
            name=op.f("ck_customers_name_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_customers_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "updated_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_customers_updater_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
        sa.UniqueConstraint(
            "tenant_id",
            "customer_code",
            name="uq_customers_tenant_customer_code",
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_customers_tenant_name"),
    )
    op.create_index(
        "ix_customers_tenant_archived_created",
        "customers",
        ["tenant_id", "archived", "created_at", "id"],
    )
    op.execute(
        "CREATE INDEX ix_customers_tenant_archived_name "
        "ON customers (tenant_id, archived, lower(name), id)"
    )
    op.execute(
        "CREATE INDEX ix_customers_search_name_trgm "
        "ON customers USING gin (lower(name) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_customers_search_phone_trgm ON customers USING gin (phone gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_customers_search_email_trgm "
        "ON customers USING gin (lower(email) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_customers_search_code_trgm "
        "ON customers USING gin (customer_code gin_trgm_ops)"
    )

    tenant_id = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    user_id = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"
    membership_check = (
        "EXISTS (SELECT 1 FROM memberships "
        "WHERE memberships.business_id = tenant_id "
        f"AND memberships.user_id = {user_id})"
    )

    for table in ("customer_code_counters", "customers"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(  # noqa: S608 -- table and policy names are migration constants.
            f"""
            CREATE POLICY {table}_tenant_access ON {table}
            FOR ALL TO distributoros_app
            USING (tenant_id = {tenant_id} AND {membership_check})
            WITH CHECK (tenant_id = {tenant_id} AND {membership_check})
            """
        )

    op.execute("GRANT SELECT, INSERT, UPDATE ON customer_code_counters TO distributoros_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON customers TO distributoros_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS customers_tenant_access ON customers")
    op.execute(
        "DROP POLICY IF EXISTS customer_code_counters_tenant_access ON customer_code_counters"
    )
    op.drop_index("ix_customers_search_code_trgm", table_name="customers")
    op.drop_index("ix_customers_search_email_trgm", table_name="customers")
    op.drop_index("ix_customers_search_phone_trgm", table_name="customers")
    op.drop_index("ix_customers_search_name_trgm", table_name="customers")
    op.drop_index("ix_customers_tenant_archived_name", table_name="customers")
    op.drop_index("ix_customers_tenant_archived_created", table_name="customers")
    op.drop_table("customers")
    op.drop_table("customer_code_counters")
