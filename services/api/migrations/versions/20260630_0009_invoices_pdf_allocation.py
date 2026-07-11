"""Add Phase 7 invoices, PDFs, and invoice payment allocation.

Revision ID: 20260630_0009
Revises: 20260630_0008
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260630_0009"
down_revision: str | None = "20260630_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invoice_number_counters",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_invoice_number_counters_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tenant_id", name=op.f("pk_invoice_number_counters")),
    )
    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(length=32), nullable=False),
        sa.Column("sale_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ledger_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("tax_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("grand_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("pdf_path", sa.String(length=500), nullable=False),
        sa.Column("sale_number_snapshot", sa.String(length=32), nullable=False),
        sa.Column("customer_name_snapshot", sa.String(length=160), nullable=False),
        sa.Column("customer_phone_snapshot", sa.String(length=32), nullable=True),
        sa.Column("customer_address_line_1_snapshot", sa.String(length=200), nullable=True),
        sa.Column("customer_address_line_2_snapshot", sa.String(length=200), nullable=True),
        sa.Column("customer_city_snapshot", sa.String(length=100), nullable=True),
        sa.Column("customer_state_snapshot", sa.String(length=100), nullable=True),
        sa.Column("customer_postal_code_snapshot", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("create_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("create_request_hash", sa.String(length=64), nullable=False),
        sa.Column("issue_idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("void_idempotency_key", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'ISSUED', 'VOID')",
            name=op.f("ck_invoices_supported_status"),
        ),
        sa.CheckConstraint("currency = 'INR'", name=op.f("ck_invoices_supported_currency")),
        sa.CheckConstraint("subtotal > 0", name=op.f("ck_invoices_subtotal_positive")),
        sa.CheckConstraint("tax_total >= 0", name=op.f("ck_invoices_tax_total_not_negative")),
        sa.CheckConstraint(
            "grand_total = subtotal + tax_total",
            name=op.f("ck_invoices_grand_total_calculated"),
        ),
        sa.CheckConstraint(
            "char_length(trim(invoice_number)) > 0",
            name=op.f("ck_invoices_invoice_number_not_blank"),
        ),
        sa.CheckConstraint(
            "char_length(trim(customer_name_snapshot)) > 0",
            name=op.f("ck_invoices_customer_snapshot_not_blank"),
        ),
        sa.CheckConstraint(
            "char_length(trim(sale_number_snapshot)) > 0",
            name=op.f("ck_invoices_sale_number_snapshot_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_invoices_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"],
            ["sales.id"],
            name=op.f("fk_invoices_sale_id_sales"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ledger_entry_id"],
            ["customer_ledger_entries.id"],
            name=op.f("fk_invoices_ledger_entry_id_customer_ledger_entries"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_invoices_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_invoices_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoices")),
        sa.UniqueConstraint(
            "tenant_id",
            "invoice_number",
            name="uq_invoices_tenant_invoice_number",
        ),
        sa.UniqueConstraint("tenant_id", "sale_id", name="uq_invoices_tenant_sale"),
        sa.UniqueConstraint(
            "tenant_id",
            "create_idempotency_key",
            name="uq_invoices_tenant_create_idempotency",
        ),
    )
    op.create_index(
        "ix_invoices_tenant_status_created",
        "invoices",
        ["tenant_id", "status", "created_at", "id"],
    )
    op.create_index(
        "ix_invoices_tenant_customer_created",
        "invoices",
        ["tenant_id", "customer_id", "created_at", "id"],
    )
    op.create_index(
        "ix_invoices_tenant_issue_date",
        "invoices",
        ["tenant_id", "issue_date", "created_at", "id"],
    )
    op.create_index("ix_invoices_tenant_sale", "invoices", ["tenant_id", "sale_id"])
    op.create_index("ix_invoices_tenant_ledger", "invoices", ["tenant_id", "ledger_entry_id"])
    op.create_index(
        "uq_invoices_tenant_issue_idempotency",
        "invoices",
        ["tenant_id", "issue_idempotency_key"],
        unique=True,
        postgresql_where=sa.text("issue_idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "uq_invoices_tenant_void_idempotency",
        "invoices",
        ["tenant_id", "void_idempotency_key"],
        unique=True,
        postgresql_where=sa.text("void_idempotency_key IS NOT NULL"),
    )
    op.execute(
        "CREATE INDEX ix_invoices_search_number_trgm "
        "ON invoices USING gin (lower(invoice_number) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_invoices_search_customer_trgm "
        "ON invoices USING gin (lower(customer_name_snapshot) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_invoices_search_sale_trgm "
        "ON invoices USING gin (lower(sale_number_snapshot) gin_trgm_ops)"
    )

    op.create_table(
        "invoice_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("product_snapshot", sa.String(length=160), nullable=False),
        sa.Column("unit_snapshot", sa.String(length=32), nullable=False),
        sa.Column("unit_price_snapshot", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("quantity_snapshot", sa.Numeric(precision=20, scale=3), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("line_number > 0", name=op.f("ck_invoice_items_line_number_positive")),
        sa.CheckConstraint(
            "quantity_snapshot > 0", name=op.f("ck_invoice_items_quantity_positive")
        ),
        sa.CheckConstraint(
            "unit_price_snapshot > 0", name=op.f("ck_invoice_items_unit_price_positive")
        ),
        sa.CheckConstraint("line_total > 0", name=op.f("ck_invoice_items_line_total_positive")),
        sa.CheckConstraint(
            "line_total = round(quantity_snapshot * unit_price_snapshot, 2)",
            name=op.f("ck_invoice_items_line_total_calculated"),
        ),
        sa.CheckConstraint(
            "char_length(trim(product_snapshot)) > 0",
            name=op.f("ck_invoice_items_product_snapshot_not_blank"),
        ),
        sa.CheckConstraint(
            "char_length(trim(unit_snapshot)) > 0",
            name=op.f("ck_invoice_items_unit_snapshot_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_invoice_items_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            name=op.f("fk_invoice_items_invoice_id_invoices"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_invoice_items_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_items")),
        sa.UniqueConstraint("invoice_id", "line_number", name="uq_invoice_items_invoice_line"),
    )
    op.create_index(
        "ix_invoice_items_tenant_invoice_line",
        "invoice_items",
        ["tenant_id", "invoice_id", "line_number"],
    )

    op.add_column(
        "payment_allocations",
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_payment_allocations_invoice_id_invoices"),
        "payment_allocations",
        "invoices",
        ["invoice_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_payment_allocations_tenant_invoice",
        "payment_allocations",
        ["tenant_id", "invoice_id", "created_at"],
    )
    op.create_index(
        "uq_payment_allocations_payment_invoice",
        "payment_allocations",
        ["tenant_id", "payment_id", "invoice_id"],
        unique=True,
        postgresql_where=sa.text("invoice_id IS NOT NULL"),
    )

    op.execute(_VALIDATE_INVOICE_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER invoices_validate
        BEFORE INSERT OR UPDATE OF tenant_id, sale_id, ledger_entry_id,
            customer_id, subtotal, tax_total, grand_total
        ON invoices
        FOR EACH ROW EXECUTE FUNCTION validate_invoice()
        """
    )
    op.execute(_IMMUTABLE_INVOICE_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER invoices_immutable
        BEFORE UPDATE OR DELETE ON invoices
        FOR EACH ROW EXECUTE FUNCTION enforce_invoice_immutable()
        """
    )
    op.execute(_VALIDATE_INVOICE_ITEM_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER invoice_items_validate
        BEFORE INSERT OR UPDATE OF tenant_id, invoice_id, product_id
        ON invoice_items
        FOR EACH ROW EXECUTE FUNCTION validate_invoice_item()
        """
    )
    op.execute(_IMMUTABLE_INVOICE_ITEM_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER invoice_items_immutable
        BEFORE UPDATE OR DELETE ON invoice_items
        FOR EACH ROW EXECUTE FUNCTION enforce_invoice_item_immutable()
        """
    )
    op.execute(_VALIDATE_PAYMENT_ALLOCATION_FUNCTION_PHASE7)

    tenant_setting = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    user_setting = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"
    membership = (
        "EXISTS (SELECT 1 FROM memberships "
        "WHERE memberships.business_id = tenant_id "
        f"AND memberships.user_id = {user_setting})"
    )
    for table in ("invoice_number_counters", "invoices", "invoice_items"):
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

    op.execute("GRANT SELECT, INSERT, UPDATE ON invoice_number_counters TO distributoros_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON invoices TO distributoros_app")
    op.execute("GRANT SELECT, INSERT ON invoice_items TO distributoros_app")
    op.execute("GRANT SELECT, INSERT ON payment_allocations TO distributoros_app")


def downgrade() -> None:
    for table in ("invoice_items", "invoices", "invoice_number_counters"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_access ON {table}")
    op.execute("DROP TRIGGER IF EXISTS invoice_items_immutable ON invoice_items")
    op.execute("DROP FUNCTION IF EXISTS enforce_invoice_item_immutable()")
    op.execute("DROP TRIGGER IF EXISTS invoice_items_validate ON invoice_items")
    op.execute("DROP FUNCTION IF EXISTS validate_invoice_item()")
    op.execute("DROP TRIGGER IF EXISTS invoices_immutable ON invoices")
    op.execute("DROP FUNCTION IF EXISTS enforce_invoice_immutable()")
    op.execute("DROP TRIGGER IF EXISTS invoices_validate ON invoices")
    op.execute("DROP FUNCTION IF EXISTS validate_invoice()")
    op.execute(_VALIDATE_PAYMENT_ALLOCATION_FUNCTION_PHASE6)
    op.drop_index("uq_payment_allocations_payment_invoice", table_name="payment_allocations")
    op.drop_index("ix_payment_allocations_tenant_invoice", table_name="payment_allocations")
    op.drop_constraint(
        op.f("fk_payment_allocations_invoice_id_invoices"),
        "payment_allocations",
        type_="foreignkey",
    )
    op.drop_column("payment_allocations", "invoice_id")
    op.drop_index("ix_invoice_items_tenant_invoice_line", table_name="invoice_items")
    op.drop_table("invoice_items")
    op.drop_index("ix_invoices_search_sale_trgm", table_name="invoices")
    op.drop_index("ix_invoices_search_customer_trgm", table_name="invoices")
    op.drop_index("ix_invoices_search_number_trgm", table_name="invoices")
    op.drop_index("uq_invoices_tenant_void_idempotency", table_name="invoices")
    op.drop_index("uq_invoices_tenant_issue_idempotency", table_name="invoices")
    op.drop_index("ix_invoices_tenant_ledger", table_name="invoices")
    op.drop_index("ix_invoices_tenant_sale", table_name="invoices")
    op.drop_index("ix_invoices_tenant_issue_date", table_name="invoices")
    op.drop_index("ix_invoices_tenant_customer_created", table_name="invoices")
    op.drop_index("ix_invoices_tenant_status_created", table_name="invoices")
    op.drop_table("invoices")
    op.drop_table("invoice_number_counters")


_VALIDATE_INVOICE_FUNCTION = """
CREATE FUNCTION validate_invoice()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    sale_tenant uuid;
    sale_customer uuid;
    sale_status text;
    sale_subtotal numeric(18, 2);
    ledger_tenant uuid;
    ledger_customer uuid;
    ledger_reference uuid;
    ledger_debit numeric(18, 2);
BEGIN
    SELECT tenant_id, customer_id, status, subtotal
    INTO sale_tenant, sale_customer, sale_status, sale_subtotal
    FROM sales WHERE id = NEW.sale_id;
    IF NOT FOUND OR sale_tenant <> NEW.tenant_id THEN
        RAISE EXCEPTION 'Sale does not belong to invoice tenant'
            USING ERRCODE = '23503', CONSTRAINT = 'fk_invoice_tenant_sale';
    END IF;
    IF sale_status <> 'POSTED' THEN
        RAISE EXCEPTION 'Only posted sales can be invoiced'
            USING ERRCODE = '23514', CONSTRAINT = 'ck_invoice_sale_posted';
    END IF;
    IF sale_customer <> NEW.customer_id THEN
        RAISE EXCEPTION 'Invoice customer must match sale customer'
            USING ERRCODE = '23514', CONSTRAINT = 'ck_invoice_sale_customer';
    END IF;
    SELECT tenant_id, customer_id, reference_id, debit
    INTO ledger_tenant, ledger_customer, ledger_reference, ledger_debit
    FROM customer_ledger_entries
    WHERE id = NEW.ledger_entry_id
      AND entry_type = 'SALE'
      AND reference_type = 'SALE';
    IF NOT FOUND
       OR ledger_tenant <> NEW.tenant_id
       OR ledger_customer <> NEW.customer_id
       OR ledger_reference <> NEW.sale_id
       OR ledger_debit <> NEW.grand_total
    THEN
        RAISE EXCEPTION 'Invoice ledger entry must match posted sale'
            USING ERRCODE = '23514', CONSTRAINT = 'ck_invoice_ledger_entry';
    END IF;
    IF NEW.subtotal <> sale_subtotal OR NEW.tax_total <> 0 OR NEW.grand_total <> sale_subtotal THEN
        RAISE EXCEPTION 'Invoice totals must match sale subtotal for Phase 7'
            USING ERRCODE = '23514', CONSTRAINT = 'ck_invoice_sale_total';
    END IF;
    RETURN NEW;
END;
$$
"""


_IMMUTABLE_INVOICE_FUNCTION = """
CREATE FUNCTION enforce_invoice_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Invoices are immutable' USING ERRCODE = '55000';
    END IF;
    IF OLD.status = 'DRAFT' AND NEW.status = 'DRAFT' THEN
        RETURN NEW;
    END IF;
    IF OLD.id IS DISTINCT FROM NEW.id
       OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
       OR OLD.invoice_number IS DISTINCT FROM NEW.invoice_number
       OR OLD.sale_id IS DISTINCT FROM NEW.sale_id
       OR OLD.ledger_entry_id IS DISTINCT FROM NEW.ledger_entry_id
       OR OLD.customer_id IS DISTINCT FROM NEW.customer_id
       OR OLD.issue_date IS DISTINCT FROM NEW.issue_date
       OR OLD.currency IS DISTINCT FROM NEW.currency
       OR OLD.subtotal IS DISTINCT FROM NEW.subtotal
       OR OLD.tax_total IS DISTINCT FROM NEW.tax_total
       OR OLD.grand_total IS DISTINCT FROM NEW.grand_total
       OR OLD.pdf_path IS DISTINCT FROM NEW.pdf_path
       OR OLD.sale_number_snapshot IS DISTINCT FROM NEW.sale_number_snapshot
       OR OLD.customer_name_snapshot IS DISTINCT FROM NEW.customer_name_snapshot
       OR OLD.customer_phone_snapshot IS DISTINCT FROM NEW.customer_phone_snapshot
       OR OLD.customer_address_line_1_snapshot IS DISTINCT FROM NEW.customer_address_line_1_snapshot
       OR OLD.customer_address_line_2_snapshot IS DISTINCT FROM NEW.customer_address_line_2_snapshot
       OR OLD.customer_city_snapshot IS DISTINCT FROM NEW.customer_city_snapshot
       OR OLD.customer_state_snapshot IS DISTINCT FROM NEW.customer_state_snapshot
       OR OLD.customer_postal_code_snapshot IS DISTINCT FROM NEW.customer_postal_code_snapshot
       OR OLD.created_at IS DISTINCT FROM NEW.created_at
       OR OLD.created_by IS DISTINCT FROM NEW.created_by
       OR OLD.create_idempotency_key IS DISTINCT FROM NEW.create_idempotency_key
       OR OLD.create_request_hash IS DISTINCT FROM NEW.create_request_hash THEN
        RAISE EXCEPTION 'Issued invoices are immutable' USING ERRCODE = '55000';
    END IF;
    IF OLD.status = 'DRAFT'
       AND NEW.status = 'ISSUED'
       AND OLD.issue_idempotency_key IS NULL
       AND NEW.issue_idempotency_key IS NOT NULL
       AND OLD.void_idempotency_key IS NOT DISTINCT FROM NEW.void_idempotency_key THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'ISSUED'
       AND NEW.status = 'VOID'
       AND OLD.void_idempotency_key IS NULL
       AND NEW.void_idempotency_key IS NOT NULL
       AND OLD.issue_idempotency_key IS NOT DISTINCT FROM NEW.issue_idempotency_key THEN
        RETURN NEW;
    END IF;
    IF OLD.status IS NOT DISTINCT FROM NEW.status
       AND OLD.issue_idempotency_key IS NOT DISTINCT FROM NEW.issue_idempotency_key
       AND OLD.void_idempotency_key IS NOT DISTINCT FROM NEW.void_idempotency_key THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Invoices can only transition DRAFT to ISSUED to VOID'
        USING ERRCODE = '55000';
END;
$$
"""


_VALIDATE_INVOICE_ITEM_FUNCTION = """
CREATE FUNCTION validate_invoice_item()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    invoice_tenant uuid;
    product_tenant uuid;
BEGIN
    SELECT tenant_id INTO invoice_tenant FROM invoices WHERE id = NEW.invoice_id;
    IF NOT FOUND OR invoice_tenant <> NEW.tenant_id THEN
        RAISE EXCEPTION 'Invoice item does not belong to invoice tenant'
            USING ERRCODE = '23503', CONSTRAINT = 'fk_invoice_item_tenant_invoice';
    END IF;
    SELECT tenant_id INTO product_tenant FROM products WHERE id = NEW.product_id;
    IF NOT FOUND OR product_tenant <> NEW.tenant_id THEN
        RAISE EXCEPTION 'Invoice item product does not belong to tenant'
            USING ERRCODE = '23503', CONSTRAINT = 'fk_invoice_item_tenant_product';
    END IF;
    RETURN NEW;
END;
$$
"""


_IMMUTABLE_INVOICE_ITEM_FUNCTION = """
CREATE FUNCTION enforce_invoice_item_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    invoice_status text;
BEGIN
    SELECT status INTO invoice_status FROM invoices WHERE id = OLD.invoice_id;
    IF invoice_status = 'DRAFT' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    RAISE EXCEPTION 'Issued invoice items are immutable' USING ERRCODE = '55000';
END;
$$
"""


_VALIDATE_PAYMENT_ALLOCATION_FUNCTION_PHASE7 = """
CREATE OR REPLACE FUNCTION validate_payment_allocation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    payment_tenant uuid;
    payment_customer uuid;
    payment_amount numeric(18, 2);
    payment_allocated numeric(18, 2);
    ledger_tenant uuid;
    ledger_customer uuid;
    ledger_reference_type text;
    ledger_reference_id uuid;
    ledger_debit numeric(18, 2);
    ledger_credit numeric(18, 2);
    ledger_allocated numeric(18, 2);
    ledger_reversed boolean;
    invoice_tenant uuid;
    invoice_customer uuid;
    invoice_ledger uuid;
    invoice_status text;
    invoice_total numeric(18, 2);
    invoice_allocated numeric(18, 2);
BEGIN
    SELECT tenant_id, customer_id, amount
    INTO payment_tenant, payment_customer, payment_amount
    FROM payments WHERE id = NEW.payment_id;
    IF NOT FOUND OR payment_tenant <> NEW.tenant_id THEN
        RAISE EXCEPTION 'Payment does not belong to allocation tenant'
            USING ERRCODE = '23503', CONSTRAINT = 'fk_allocation_tenant_payment';
    END IF;
    SELECT tenant_id, customer_id, reference_type, reference_id, debit, credit
    INTO ledger_tenant, ledger_customer, ledger_reference_type, ledger_reference_id,
         ledger_debit, ledger_credit
    FROM customer_ledger_entries WHERE id = NEW.ledger_entry_id;
    IF NOT FOUND
       OR ledger_tenant <> NEW.tenant_id
       OR ledger_customer <> payment_customer
       OR ledger_debit <= 0
       OR ledger_credit <> 0 THEN
        RAISE EXCEPTION 'Allocation target does not belong to payment customer'
            USING ERRCODE = '23503', CONSTRAINT = 'fk_allocation_tenant_ledger';
    END IF;
    SELECT EXISTS (
        SELECT 1
        FROM customer_ledger_entries reversal
        WHERE reversal.tenant_id = NEW.tenant_id
          AND reversal.customer_id = ledger_customer
          AND reversal.reference_type = ledger_reference_type
          AND reversal.reference_id = ledger_reference_id
          AND reversal.entry_type IN ('REVERSAL', 'PAYMENT_REVERSAL')
    )
    INTO ledger_reversed;
    IF ledger_reversed THEN
        RAISE EXCEPTION 'Allocation target is no longer open'
            USING ERRCODE = '23514', CONSTRAINT = 'ck_allocation_target_open';
    END IF;
    IF NEW.invoice_id IS NOT NULL THEN
        SELECT tenant_id, customer_id, ledger_entry_id, status, grand_total
        INTO invoice_tenant, invoice_customer, invoice_ledger, invoice_status, invoice_total
        FROM invoices WHERE id = NEW.invoice_id;
        IF NOT FOUND
           OR invoice_tenant <> NEW.tenant_id
           OR invoice_customer <> payment_customer
           OR invoice_ledger <> NEW.ledger_entry_id
           OR invoice_status <> 'ISSUED' THEN
            RAISE EXCEPTION
                'Invoice allocation target must be an issued invoice for the payment customer'
                USING ERRCODE = '23503', CONSTRAINT = 'fk_allocation_tenant_invoice';
        END IF;
        SELECT COALESCE(SUM(pa.allocated_amount), 0)
        INTO invoice_allocated
        FROM payment_allocations pa
        JOIN payments p ON p.id = pa.payment_id AND p.tenant_id = pa.tenant_id
        WHERE pa.tenant_id = NEW.tenant_id
          AND pa.invoice_id = NEW.invoice_id
          AND p.status = 'POSTED';
        IF invoice_allocated + NEW.allocated_amount > invoice_total THEN
            RAISE EXCEPTION 'Invoice allocation exceeds invoice outstanding amount'
                USING ERRCODE = '23514', CONSTRAINT = 'ck_invoice_allocation_amount_available';
        END IF;
    END IF;
    SELECT COALESCE(SUM(pa.allocated_amount), 0)
    INTO payment_allocated
    FROM payment_allocations pa
    JOIN payments p ON p.id = pa.payment_id AND p.tenant_id = pa.tenant_id
    JOIN customer_ledger_entries target
      ON target.id = pa.ledger_entry_id AND target.tenant_id = pa.tenant_id
    LEFT JOIN invoices target_invoice
      ON target_invoice.id = pa.invoice_id AND target_invoice.tenant_id = pa.tenant_id
    WHERE pa.tenant_id = NEW.tenant_id
      AND pa.payment_id = NEW.payment_id
      AND p.status = 'POSTED'
      AND (pa.invoice_id IS NULL OR target_invoice.status = 'ISSUED')
      AND NOT EXISTS (
          SELECT 1
          FROM customer_ledger_entries reversal
          WHERE reversal.tenant_id = target.tenant_id
            AND reversal.customer_id = target.customer_id
            AND reversal.reference_type = target.reference_type
            AND reversal.reference_id = target.reference_id
            AND reversal.entry_type IN ('REVERSAL', 'PAYMENT_REVERSAL')
      );
    IF payment_allocated + NEW.allocated_amount > payment_amount THEN
        RAISE EXCEPTION 'Allocation amount exceeds payment amount'
            USING ERRCODE = '23514', CONSTRAINT = 'ck_payment_allocation_amount_available';
    END IF;
    SELECT COALESCE(SUM(pa.allocated_amount), 0)
    INTO ledger_allocated
    FROM payment_allocations pa
    JOIN payments p ON p.id = pa.payment_id AND p.tenant_id = pa.tenant_id
    LEFT JOIN invoices target_invoice
      ON target_invoice.id = pa.invoice_id AND target_invoice.tenant_id = pa.tenant_id
    WHERE pa.tenant_id = NEW.tenant_id
      AND pa.ledger_entry_id = NEW.ledger_entry_id
      AND p.status = 'POSTED'
      AND (pa.invoice_id IS NULL OR target_invoice.status = 'ISSUED');
    IF ledger_allocated + NEW.allocated_amount > ledger_debit THEN
        RAISE EXCEPTION 'Allocation amount exceeds ledger amount'
            USING ERRCODE = '23514', CONSTRAINT = 'ck_allocation_amount_available';
    END IF;
    RETURN NEW;
END;
$$
"""


_VALIDATE_PAYMENT_ALLOCATION_FUNCTION_PHASE6 = """
CREATE OR REPLACE FUNCTION validate_payment_allocation()
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
