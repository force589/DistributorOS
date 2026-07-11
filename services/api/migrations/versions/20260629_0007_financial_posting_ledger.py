"""Add Phase 5B immutable customer ledger and balance projection.

Revision ID: 20260629_0007
Revises: 20260629_0006
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260629_0007"
down_revision: str | None = "20260629_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_ledger_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("reference_type", sa.String(length=32), nullable=False),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("debit", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("credit", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "entry_type IN ('SALE', 'REVERSAL')",
            name=op.f("ck_customer_ledger_entries_supported_entry_type"),
        ),
        sa.CheckConstraint(
            "reference_type = 'SALE'",
            name=op.f("ck_customer_ledger_entries_supported_reference_type"),
        ),
        sa.CheckConstraint(
            "debit >= 0 AND credit >= 0",
            name=op.f("ck_customer_ledger_entries_amounts_not_negative"),
        ),
        sa.CheckConstraint(
            "(entry_type = 'SALE' AND debit > 0 AND credit = 0) OR "
            "(entry_type = 'REVERSAL' AND debit = 0 AND credit > 0)",
            name=op.f("ck_customer_ledger_entries_entry_direction"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_customer_ledger_entries_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_customer_ledger_entries_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_ledger_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_ledger_entries")),
        sa.UniqueConstraint(
            "tenant_id",
            "entry_type",
            "reference_type",
            "reference_id",
            name="uq_ledger_tenant_type_reference",
        ),
    )
    op.create_index(
        "ix_ledger_tenant_customer_created",
        "customer_ledger_entries",
        ["tenant_id", "customer_id", "created_at", "id"],
    )
    op.create_index(
        "ix_ledger_tenant_type_created",
        "customer_ledger_entries",
        ["tenant_id", "entry_type", "created_at", "id"],
    )
    op.create_index(
        "ix_ledger_tenant_reference",
        "customer_ledger_entries",
        ["tenant_id", "reference_type", "reference_id"],
    )

    op.create_table(
        "customer_balance_projections",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("outstanding_balance", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("total_sales", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("last_sale_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outstanding_balance >= 0",
            name=op.f("ck_customer_balance_projections_outstanding_not_negative"),
        ),
        sa.CheckConstraint(
            "total_sales >= 0",
            name=op.f("ck_customer_balance_projections_total_sales_not_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_customer_balance_projections_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_customer_balance_projections_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "customer_id",
            name=op.f("pk_customer_balance_projections"),
        ),
    )
    op.create_index(
        "ix_customer_balances_tenant_outstanding",
        "customer_balance_projections",
        ["tenant_id", "outstanding_balance", "customer_id"],
    )

    op.execute(
        """
        CREATE FUNCTION validate_customer_ledger_entry()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            customer_tenant uuid;
            sale_tenant uuid;
            sale_customer uuid;
            sale_subtotal numeric(18, 2);
        BEGIN
            SELECT tenant_id INTO customer_tenant
            FROM customers WHERE id = NEW.customer_id;
            IF NOT FOUND OR customer_tenant <> NEW.tenant_id THEN
                RAISE EXCEPTION 'Customer does not belong to ledger tenant'
                    USING ERRCODE = '23503', CONSTRAINT = 'fk_ledger_tenant_customer';
            END IF;
            SELECT tenant_id, customer_id, subtotal
            INTO sale_tenant, sale_customer, sale_subtotal
            FROM sales WHERE id = NEW.reference_id;
            IF NOT FOUND
               OR NEW.reference_type <> 'SALE'
               OR sale_tenant <> NEW.tenant_id
               OR sale_customer <> NEW.customer_id
            THEN
                RAISE EXCEPTION 'Sale reference does not belong to ledger customer'
                    USING ERRCODE = '23503', CONSTRAINT = 'fk_ledger_tenant_sale';
            END IF;
            IF NEW.entry_type = 'SALE' THEN
                IF NEW.debit <> sale_subtotal OR NEW.credit <> 0 THEN
                    RAISE EXCEPTION 'Sale ledger amount must match sale subtotal'
                        USING ERRCODE = '23514', CONSTRAINT = 'ck_ledger_sale_amount';
                END IF;
            ELSIF NEW.entry_type = 'REVERSAL' THEN
                IF NEW.credit <> sale_subtotal OR NEW.debit <> 0 OR NOT EXISTS (
                    SELECT 1 FROM customer_ledger_entries original
                    WHERE original.tenant_id = NEW.tenant_id
                      AND original.customer_id = NEW.customer_id
                      AND original.entry_type = 'SALE'
                      AND original.reference_type = NEW.reference_type
                      AND original.reference_id = NEW.reference_id
                ) THEN
                    RAISE EXCEPTION 'Reversal must exactly offset an existing sale entry'
                        USING ERRCODE = '23514', CONSTRAINT = 'ck_ledger_reversal_amount';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER customer_ledger_validate
        BEFORE INSERT ON customer_ledger_entries
        FOR EACH ROW EXECUTE FUNCTION validate_customer_ledger_entry()
        """
    )
    op.execute(
        """
        CREATE FUNCTION enforce_customer_ledger_immutable()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'Customer ledger entries are immutable' USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER customer_ledger_immutable
        BEFORE UPDATE OR DELETE ON customer_ledger_entries
        FOR EACH ROW EXECUTE FUNCTION enforce_customer_ledger_immutable()
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_customer_balance_projection()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            customer_tenant uuid;
        BEGIN
            SELECT tenant_id INTO customer_tenant
            FROM customers WHERE id = NEW.customer_id;
            IF NOT FOUND OR customer_tenant <> NEW.tenant_id THEN
                RAISE EXCEPTION 'Customer does not belong to balance tenant'
                    USING ERRCODE = '23503', CONSTRAINT = 'fk_balance_tenant_customer';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER customer_balance_validate
        BEFORE INSERT OR UPDATE OF tenant_id, customer_id
        ON customer_balance_projections
        FOR EACH ROW EXECUTE FUNCTION validate_customer_balance_projection()
        """
    )

    tenant_setting = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    user_setting = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"
    maintenance = "current_setting('app.internal_maintenance', true) = 'true'"
    membership = (
        "EXISTS (SELECT 1 FROM memberships "
        "WHERE memberships.business_id = tenant_id "
        f"AND memberships.user_id = {user_setting})"
    )
    for table in ("customer_ledger_entries", "customer_balance_projections"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(  # noqa: S608 -- migration names are fixed constants.
            f"""
            CREATE POLICY {table}_tenant_access ON {table}
            FOR ALL
            USING ({maintenance} OR (tenant_id = {tenant_setting} AND {membership}))
            WITH CHECK ({maintenance} OR (tenant_id = {tenant_setting} AND {membership}))
            """
        )

    op.execute("SELECT set_config('app.internal_maintenance', 'true', true)")

    op.execute(
        """
        INSERT INTO customer_ledger_entries (
            id, tenant_id, customer_id, entry_type, reference_type,
            reference_id, debit, credit, remarks, created_at, created_by
        )
        SELECT
            gen_random_uuid(), tenant_id, customer_id, 'SALE', 'SALE',
            id, subtotal, 0, NULL, created_at, created_by
        FROM sales
        WHERE status IN ('POSTED', 'VOID')
        """
    )
    op.execute(
        """
        INSERT INTO customer_ledger_entries (
            id, tenant_id, customer_id, entry_type, reference_type,
            reference_id, debit, credit, remarks, created_at, created_by
        )
        SELECT
            gen_random_uuid(), tenant_id, customer_id, 'REVERSAL', 'SALE',
            id, 0, subtotal, NULL, updated_at, created_by
        FROM sales
        WHERE status = 'VOID'
        """
    )
    op.execute(
        """
        INSERT INTO customer_balance_projections (
            tenant_id, customer_id, outstanding_balance,
            total_sales, last_sale_at, updated_at
        )
        SELECT
            tenant_id,
            customer_id,
            sum(debit - credit),
            sum(CASE WHEN entry_type = 'SALE' THEN debit ELSE -credit END),
            max(created_at) FILTER (WHERE entry_type = 'SALE'),
            now()
        FROM customer_ledger_entries
        GROUP BY tenant_id, customer_id
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS customer_balance_projections_tenant_access "
        "ON customer_balance_projections"
    )
    op.execute(
        "DROP POLICY IF EXISTS customer_ledger_entries_tenant_access ON customer_ledger_entries"
    )
    op.execute("DROP TRIGGER IF EXISTS customer_balance_validate ON customer_balance_projections")
    op.execute("DROP FUNCTION IF EXISTS validate_customer_balance_projection()")
    op.execute("DROP TRIGGER IF EXISTS customer_ledger_immutable ON customer_ledger_entries")
    op.execute("DROP FUNCTION IF EXISTS enforce_customer_ledger_immutable()")
    op.execute("DROP TRIGGER IF EXISTS customer_ledger_validate ON customer_ledger_entries")
    op.execute("DROP FUNCTION IF EXISTS validate_customer_ledger_entry()")
    op.drop_index(
        "ix_customer_balances_tenant_outstanding",
        table_name="customer_balance_projections",
    )
    op.drop_table("customer_balance_projections")
    op.drop_index("ix_ledger_tenant_reference", table_name="customer_ledger_entries")
    op.drop_index("ix_ledger_tenant_type_created", table_name="customer_ledger_entries")
    op.drop_index("ix_ledger_tenant_customer_created", table_name="customer_ledger_entries")
    op.drop_table("customer_ledger_entries")
