"""Add Phase 6 customer payments and payment allocation.

Revision ID: 20260630_0008
Revises: 20260629_0007
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260630_0008"
down_revision: str | None = "20260629_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "customer_balance_projections",
        sa.Column(
            "available_credit",
            sa.Numeric(precision=18, scale=2),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "customer_balance_projections",
        sa.Column(
            "total_payments",
            sa.Numeric(precision=18, scale=2),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "customer_balance_projections",
        sa.Column("last_payment_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        "customer_balance_projections",
        "available_credit",
        server_default=None,
    )
    op.alter_column(
        "customer_balance_projections",
        "total_payments",
        server_default=None,
    )
    op.create_check_constraint(
        op.f("ck_customer_balance_projections_available_credit_not_negative"),
        "customer_balance_projections",
        "available_credit >= 0",
    )
    op.create_check_constraint(
        op.f("ck_customer_balance_projections_balance_or_credit_not_both"),
        "customer_balance_projections",
        "NOT (outstanding_balance > 0 AND available_credit > 0)",
    )
    op.create_check_constraint(
        op.f("ck_customer_balance_projections_total_payments_not_negative"),
        "customer_balance_projections",
        "total_payments >= 0",
    )
    op.create_index(
        "ix_customer_balances_tenant_credit",
        "customer_balance_projections",
        ["tenant_id", "available_credit", "customer_id"],
    )

    op.drop_constraint(
        op.f("ck_customer_ledger_entries_entry_direction"),
        "customer_ledger_entries",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_customer_ledger_entries_supported_reference_type"),
        "customer_ledger_entries",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_customer_ledger_entries_supported_entry_type"),
        "customer_ledger_entries",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_customer_ledger_entries_supported_entry_type"),
        "customer_ledger_entries",
        "entry_type IN ('SALE', 'REVERSAL', 'PAYMENT', 'PAYMENT_REVERSAL')",
    )
    op.create_check_constraint(
        op.f("ck_customer_ledger_entries_supported_reference_type"),
        "customer_ledger_entries",
        "reference_type IN ('SALE', 'PAYMENT')",
    )
    op.create_check_constraint(
        op.f("ck_customer_ledger_entries_entry_direction"),
        "customer_ledger_entries",
        "(entry_type = 'SALE' AND debit > 0 AND credit = 0) OR "
        "(entry_type = 'REVERSAL' AND debit = 0 AND credit > 0) OR "
        "(entry_type = 'PAYMENT' AND debit = 0 AND credit > 0) OR "
        "(entry_type = 'PAYMENT_REVERSAL' AND debit > 0 AND credit = 0)",
    )

    op.create_table(
        "payment_number_counters",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_payment_number_counters_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tenant_id", name=op.f("pk_payment_number_counters")),
    )
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_number", sa.String(length=32), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("payment_method", sa.String(length=32), nullable=False),
        sa.Column("reference_number", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("create_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("create_request_hash", sa.String(length=64), nullable=False),
        sa.Column("void_idempotency_key", sa.String(length=128), nullable=True),
        sa.CheckConstraint("amount > 0", name=op.f("ck_payments_amount_positive")),
        sa.CheckConstraint(
            "payment_method IN ('cash', 'upi', 'bank_transfer', 'cheque', 'other')",
            name=op.f("ck_payments_supported_payment_method"),
        ),
        sa.CheckConstraint(
            "status IN ('POSTED', 'VOID')",
            name=op.f("ck_payments_supported_status"),
        ),
        sa.CheckConstraint(
            "char_length(trim(payment_number)) > 0",
            name=op.f("ck_payments_payment_number_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_payments_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_payments_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_payments_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint(
            "tenant_id",
            "payment_number",
            name="uq_payments_tenant_payment_number",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "create_idempotency_key",
            name="uq_payments_tenant_create_idempotency",
        ),
    )
    op.create_index(
        "ix_payments_tenant_status_created",
        "payments",
        ["tenant_id", "status", "created_at", "id"],
    )
    op.create_index(
        "ix_payments_tenant_customer_created",
        "payments",
        ["tenant_id", "customer_id", "created_at", "id"],
    )
    op.create_index(
        "ix_payments_tenant_method_created",
        "payments",
        ["tenant_id", "payment_method", "created_at", "id"],
    )
    op.create_index(
        "ix_payments_tenant_payment_date",
        "payments",
        ["tenant_id", "payment_date", "created_at", "id"],
    )
    op.create_index(
        "uq_payments_tenant_void_idempotency",
        "payments",
        ["tenant_id", "void_idempotency_key"],
        unique=True,
        postgresql_where=sa.text("void_idempotency_key IS NOT NULL"),
    )
    op.execute(
        "CREATE INDEX ix_payments_search_number_trgm "
        "ON payments USING gin (lower(payment_number) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_payments_search_reference_trgm "
        "ON payments USING gin (lower(reference_number) gin_trgm_ops) "
        "WHERE reference_number IS NOT NULL"
    )
    op.create_table(
        "payment_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ledger_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "allocated_amount > 0",
            name=op.f("ck_payment_allocations_allocated_amount_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_payment_allocations_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_allocations_payment_id_payments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ledger_entry_id"],
            ["customer_ledger_entries.id"],
            name=op.f("fk_payment_allocations_ledger_entry_id_customer_ledger_entries"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_allocations")),
        sa.UniqueConstraint(
            "tenant_id",
            "payment_id",
            "ledger_entry_id",
            name="uq_payment_allocations_payment_ledger",
        ),
    )
    op.create_index(
        "ix_payment_allocations_tenant_payment",
        "payment_allocations",
        ["tenant_id", "payment_id", "created_at"],
    )
    op.create_index(
        "ix_payment_allocations_tenant_ledger",
        "payment_allocations",
        ["tenant_id", "ledger_entry_id", "created_at"],
    )

    op.execute(_VALIDATE_PAYMENT_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER payments_validate
        BEFORE INSERT OR UPDATE OF tenant_id, customer_id
        ON payments
        FOR EACH ROW EXECUTE FUNCTION validate_payment()
        """
    )
    op.execute(_IMMUTABLE_PAYMENT_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER payments_immutable
        BEFORE UPDATE OR DELETE ON payments
        FOR EACH ROW EXECUTE FUNCTION enforce_payment_immutable()
        """
    )
    op.execute(_VALIDATE_PAYMENT_ALLOCATION_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER payment_allocations_validate
        BEFORE INSERT ON payment_allocations
        FOR EACH ROW EXECUTE FUNCTION validate_payment_allocation()
        """
    )
    op.execute(_IMMUTABLE_PAYMENT_ALLOCATION_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER payment_allocations_immutable
        BEFORE UPDATE OR DELETE ON payment_allocations
        FOR EACH ROW EXECUTE FUNCTION enforce_payment_allocation_immutable()
        """
    )
    op.execute(_VALIDATE_LEDGER_FUNCTION_PHASE6)

    tenant_setting = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    user_setting = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"
    membership = (
        "EXISTS (SELECT 1 FROM memberships "
        "WHERE memberships.business_id = tenant_id "
        f"AND memberships.user_id = {user_setting})"
    )
    for table in ("payment_number_counters", "payments", "payment_allocations"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_access ON {table}
            FOR ALL TO distributoros_app
            USING (tenant_id = {tenant_setting} AND {membership})
            WITH CHECK (tenant_id = {tenant_setting} AND {membership})
            """
        )

    op.execute("GRANT SELECT, INSERT, UPDATE ON payment_number_counters TO distributoros_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON payments TO distributoros_app")
    op.execute("GRANT SELECT, INSERT ON payment_allocations TO distributoros_app")


def downgrade() -> None:
    for table in ("payment_allocations", "payments", "payment_number_counters"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_access ON {table}")
    op.execute("DROP TRIGGER IF EXISTS payment_allocations_immutable ON payment_allocations")
    op.execute("DROP FUNCTION IF EXISTS enforce_payment_allocation_immutable()")
    op.execute("DROP TRIGGER IF EXISTS payment_allocations_validate ON payment_allocations")
    op.execute("DROP FUNCTION IF EXISTS validate_payment_allocation()")
    op.execute("DROP TRIGGER IF EXISTS payments_immutable ON payments")
    op.execute("DROP FUNCTION IF EXISTS enforce_payment_immutable()")
    op.execute("DROP TRIGGER IF EXISTS payments_validate ON payments")
    op.execute("DROP FUNCTION IF EXISTS validate_payment()")
    op.drop_index("ix_payment_allocations_tenant_ledger", table_name="payment_allocations")
    op.drop_index("ix_payment_allocations_tenant_payment", table_name="payment_allocations")
    op.drop_table("payment_allocations")
    op.drop_index("ix_payments_search_reference_trgm", table_name="payments")
    op.drop_index("ix_payments_search_number_trgm", table_name="payments")
    op.drop_index("uq_payments_tenant_void_idempotency", table_name="payments")
    op.drop_index("ix_payments_tenant_payment_date", table_name="payments")
    op.drop_index("ix_payments_tenant_method_created", table_name="payments")
    op.drop_index("ix_payments_tenant_customer_created", table_name="payments")
    op.drop_index("ix_payments_tenant_status_created", table_name="payments")
    op.drop_table("payments")
    op.drop_table("payment_number_counters")

    op.drop_constraint(
        op.f("ck_customer_ledger_entries_entry_direction"),
        "customer_ledger_entries",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_customer_ledger_entries_supported_reference_type"),
        "customer_ledger_entries",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_customer_ledger_entries_supported_entry_type"),
        "customer_ledger_entries",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_customer_ledger_entries_supported_entry_type"),
        "customer_ledger_entries",
        "entry_type IN ('SALE', 'REVERSAL')",
    )
    op.create_check_constraint(
        op.f("ck_customer_ledger_entries_supported_reference_type"),
        "customer_ledger_entries",
        "reference_type = 'SALE'",
    )
    op.create_check_constraint(
        op.f("ck_customer_ledger_entries_entry_direction"),
        "customer_ledger_entries",
        "(entry_type = 'SALE' AND debit > 0 AND credit = 0) OR "
        "(entry_type = 'REVERSAL' AND debit = 0 AND credit > 0)",
    )
    op.execute(_VALIDATE_LEDGER_FUNCTION_PHASE5)

    op.drop_index("ix_customer_balances_tenant_credit", table_name="customer_balance_projections")
    op.drop_constraint(
        op.f("ck_customer_balance_projections_total_payments_not_negative"),
        "customer_balance_projections",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_customer_balance_projections_balance_or_credit_not_both"),
        "customer_balance_projections",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_customer_balance_projections_available_credit_not_negative"),
        "customer_balance_projections",
        type_="check",
    )
    op.drop_column("customer_balance_projections", "last_payment_at")
    op.drop_column("customer_balance_projections", "total_payments")
    op.drop_column("customer_balance_projections", "available_credit")


_VALIDATE_PAYMENT_FUNCTION = """
CREATE FUNCTION validate_payment()
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
        RAISE EXCEPTION 'Customer does not belong to payment tenant'
            USING ERRCODE = '23503', CONSTRAINT = 'fk_payment_tenant_customer';
    END IF;
    RETURN NEW;
END;
$$
"""


_IMMUTABLE_PAYMENT_FUNCTION = """
CREATE FUNCTION enforce_payment_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Payments are immutable' USING ERRCODE = '55000';
    END IF;
    IF OLD.id IS DISTINCT FROM NEW.id
       OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
       OR OLD.payment_number IS DISTINCT FROM NEW.payment_number
       OR OLD.customer_id IS DISTINCT FROM NEW.customer_id
       OR OLD.payment_date IS DISTINCT FROM NEW.payment_date
       OR OLD.amount IS DISTINCT FROM NEW.amount
       OR OLD.payment_method IS DISTINCT FROM NEW.payment_method
       OR OLD.reference_number IS DISTINCT FROM NEW.reference_number
       OR OLD.notes IS DISTINCT FROM NEW.notes
       OR OLD.created_at IS DISTINCT FROM NEW.created_at
       OR OLD.created_by IS DISTINCT FROM NEW.created_by
       OR OLD.create_idempotency_key IS DISTINCT FROM NEW.create_idempotency_key
       OR OLD.create_request_hash IS DISTINCT FROM NEW.create_request_hash THEN
        RAISE EXCEPTION 'Payments are immutable' USING ERRCODE = '55000';
    END IF;
    IF OLD.status = 'POSTED'
       AND NEW.status = 'VOID'
       AND OLD.void_idempotency_key IS NULL
       AND NEW.void_idempotency_key IS NOT NULL THEN
        RETURN NEW;
    END IF;
    IF OLD.status IS NOT DISTINCT FROM NEW.status
       AND OLD.void_idempotency_key IS NOT DISTINCT FROM NEW.void_idempotency_key THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Payments can only transition from POSTED to VOID'
        USING ERRCODE = '55000';
END;
$$
"""


_VALIDATE_PAYMENT_ALLOCATION_FUNCTION = """
CREATE FUNCTION validate_payment_allocation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    payment_tenant uuid;
    payment_customer uuid;
    payment_amount numeric(18, 2);
    ledger_tenant uuid;
    ledger_customer uuid;
    ledger_debit numeric(18, 2);
    ledger_credit numeric(18, 2);
BEGIN
    SELECT tenant_id, customer_id, amount
    INTO payment_tenant, payment_customer, payment_amount
    FROM payments WHERE id = NEW.payment_id;
    IF NOT FOUND OR payment_tenant <> NEW.tenant_id THEN
        RAISE EXCEPTION 'Payment does not belong to allocation tenant'
            USING ERRCODE = '23503', CONSTRAINT = 'fk_allocation_tenant_payment';
    END IF;
    SELECT tenant_id, customer_id, debit, credit
    INTO ledger_tenant, ledger_customer, ledger_debit, ledger_credit
    FROM customer_ledger_entries WHERE id = NEW.ledger_entry_id;
    IF NOT FOUND
       OR ledger_tenant <> NEW.tenant_id
       OR ledger_customer <> payment_customer
       OR ledger_debit <= 0
       OR ledger_credit <> 0 THEN
        RAISE EXCEPTION 'Allocation target does not belong to payment customer'
            USING ERRCODE = '23503', CONSTRAINT = 'fk_allocation_tenant_ledger';
    END IF;
    IF NEW.allocated_amount > payment_amount OR NEW.allocated_amount > ledger_debit THEN
        RAISE EXCEPTION 'Allocation amount exceeds payment or ledger amount'
            USING ERRCODE = '23514', CONSTRAINT = 'ck_allocation_amount_available';
    END IF;
    RETURN NEW;
END;
$$
"""


_IMMUTABLE_PAYMENT_ALLOCATION_FUNCTION = """
CREATE FUNCTION enforce_payment_allocation_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Payment allocations are immutable' USING ERRCODE = '55000';
END;
$$
"""


_VALIDATE_LEDGER_FUNCTION_PHASE6 = """
CREATE OR REPLACE FUNCTION validate_customer_ledger_entry()
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
    payment_tenant uuid;
    payment_customer uuid;
    payment_amount numeric(18, 2);
BEGIN
    SELECT tenant_id INTO customer_tenant
    FROM customers WHERE id = NEW.customer_id;
    IF NOT FOUND OR customer_tenant <> NEW.tenant_id THEN
        RAISE EXCEPTION 'Customer does not belong to ledger tenant'
            USING ERRCODE = '23503', CONSTRAINT = 'fk_ledger_tenant_customer';
    END IF;
    IF NEW.reference_type = 'SALE' THEN
        IF NEW.entry_type NOT IN ('SALE', 'REVERSAL') THEN
            RAISE EXCEPTION 'Sale references require sale ledger entries'
                USING ERRCODE = '23514', CONSTRAINT = 'ck_ledger_sale_reference_type';
        END IF;
        SELECT tenant_id, customer_id, subtotal
        INTO sale_tenant, sale_customer, sale_subtotal
        FROM sales WHERE id = NEW.reference_id;
        IF NOT FOUND
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
    ELSIF NEW.reference_type = 'PAYMENT' THEN
        IF NEW.entry_type NOT IN ('PAYMENT', 'PAYMENT_REVERSAL') THEN
            RAISE EXCEPTION 'Payment references require payment ledger entries'
                USING ERRCODE = '23514', CONSTRAINT = 'ck_ledger_payment_reference_type';
        END IF;
        SELECT tenant_id, customer_id, amount
        INTO payment_tenant, payment_customer, payment_amount
        FROM payments WHERE id = NEW.reference_id;
        IF NOT FOUND
           OR payment_tenant <> NEW.tenant_id
           OR payment_customer <> NEW.customer_id
        THEN
            RAISE EXCEPTION 'Payment reference does not belong to ledger customer'
                USING ERRCODE = '23503', CONSTRAINT = 'fk_ledger_tenant_payment';
        END IF;
        IF NEW.entry_type = 'PAYMENT' THEN
            IF NEW.credit <> payment_amount OR NEW.debit <> 0 THEN
                RAISE EXCEPTION 'Payment ledger amount must match payment amount'
                    USING ERRCODE = '23514', CONSTRAINT = 'ck_ledger_payment_amount';
            END IF;
        ELSIF NEW.entry_type = 'PAYMENT_REVERSAL' THEN
            IF NEW.debit <> payment_amount OR NEW.credit <> 0 OR NOT EXISTS (
                SELECT 1 FROM customer_ledger_entries original
                WHERE original.tenant_id = NEW.tenant_id
                  AND original.customer_id = NEW.customer_id
                  AND original.entry_type = 'PAYMENT'
                  AND original.reference_type = NEW.reference_type
                  AND original.reference_id = NEW.reference_id
            ) THEN
                RAISE EXCEPTION 'Payment reversal must exactly offset an existing payment entry'
                    USING ERRCODE = '23514', CONSTRAINT = 'ck_ledger_payment_reversal_amount';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$
"""


_VALIDATE_LEDGER_FUNCTION_PHASE5 = """
CREATE OR REPLACE FUNCTION validate_customer_ledger_entry()
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
