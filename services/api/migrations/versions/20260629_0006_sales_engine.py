"""Add Phase 5A sales engine.

Revision ID: 20260629_0006
Revises: 20260628_0005
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260629_0006"
down_revision: str | None = "20260628_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sale_code_counters",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_sale_code_counters_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tenant_id", name=op.f("pk_sale_code_counters")),
    )
    op.create_table(
        "sales",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sale_number", sa.String(length=32), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("create_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("create_request_hash", sa.String(length=64), nullable=False),
        sa.Column("post_idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("void_idempotency_key", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'POSTED', 'VOID')",
            name=op.f("ck_sales_supported_status"),
        ),
        sa.CheckConstraint("subtotal > 0", name=op.f("ck_sales_subtotal_positive")),
        sa.CheckConstraint(
            "char_length(create_request_hash) = 64",
            name=op.f("ck_sales_create_request_hash_length"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_sales_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_sales_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_sales_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sales")),
        sa.UniqueConstraint(
            "tenant_id",
            "create_idempotency_key",
            name="uq_sales_tenant_create_idempotency",
        ),
        sa.UniqueConstraint("tenant_id", "sale_number", name="uq_sales_tenant_sale_number"),
    )
    op.create_index(
        "ix_sales_tenant_status_created",
        "sales",
        ["tenant_id", "status", "created_at", "id"],
    )
    op.create_index(
        "ix_sales_tenant_customer_created",
        "sales",
        ["tenant_id", "customer_id", "created_at", "id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_sales_tenant_post_idempotency "
        "ON sales (tenant_id, post_idempotency_key) "
        "WHERE post_idempotency_key IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_sales_tenant_void_idempotency "
        "ON sales (tenant_id, void_idempotency_key) "
        "WHERE void_idempotency_key IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_sales_search_number_trgm "
        "ON sales USING gin (lower(sale_number) gin_trgm_ops)"
    )

    op.create_table(
        "sale_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sale_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=3), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("product_name_snapshot", sa.String(length=160), nullable=False),
        sa.Column("unit_snapshot", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_sale_items_quantity_positive")),
        sa.CheckConstraint("line_number > 0", name=op.f("ck_sale_items_line_number_positive")),
        sa.CheckConstraint("unit_price > 0", name=op.f("ck_sale_items_unit_price_positive")),
        sa.CheckConstraint("line_total > 0", name=op.f("ck_sale_items_line_total_positive")),
        sa.CheckConstraint(
            "line_total = round(quantity * unit_price, 2)",
            name=op.f("ck_sale_items_line_total_calculated"),
        ),
        sa.CheckConstraint(
            "char_length(trim(product_name_snapshot)) > 0",
            name=op.f("ck_sale_items_product_snapshot_not_blank"),
        ),
        sa.CheckConstraint(
            "char_length(trim(unit_snapshot)) > 0",
            name=op.f("ck_sale_items_unit_snapshot_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_sale_items_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"],
            ["sales.id"],
            name=op.f("fk_sale_items_sale_id_sales"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sale_items")),
        sa.UniqueConstraint("sale_id", "line_number", name="uq_sale_items_sale_line_number"),
        sa.UniqueConstraint("sale_id", "product_id", name="uq_sale_items_sale_product"),
    )
    op.create_index("ix_sale_items_sale_line", "sale_items", ["sale_id", "line_number"])

    op.execute(
        "ALTER TABLE stock_movements DROP CONSTRAINT ck_stock_movements_supported_movement_type"
    )
    op.execute("ALTER TABLE stock_movements DROP CONSTRAINT ck_stock_movements_direction")
    op.execute(
        """
        ALTER TABLE stock_movements ADD CONSTRAINT ck_stock_movements_supported_movement_type
        CHECK (movement_type IN (
            'OPENING_STOCK', 'STOCK_RECEIPT', 'STOCK_ADJUSTMENT',
            'CUSTOMER_RETURN', 'DAMAGED', 'SPOILAGE', 'SALE', 'SALE_VOID'
        ))
        """
    )
    op.execute(
        """
        ALTER TABLE stock_movements ADD CONSTRAINT ck_stock_movements_direction
        CHECK (
            (movement_type IN ('DAMAGED', 'SPOILAGE', 'SALE') AND quantity < 0)
            OR (movement_type IN (
                'OPENING_STOCK', 'STOCK_RECEIPT', 'CUSTOMER_RETURN', 'SALE_VOID'
            ) AND quantity > 0)
            OR movement_type = 'STOCK_ADJUSTMENT'
        )
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_inventory_tenant_product()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            product_tenant uuid;
            product_unit text;
            product_archived boolean;
        BEGIN
            SELECT tenant_id, unit, archived
            INTO product_tenant, product_unit, product_archived
            FROM products WHERE id = NEW.product_id;
            IF NOT FOUND OR product_tenant <> NEW.tenant_id THEN
                RAISE EXCEPTION 'Product does not belong to inventory tenant'
                    USING ERRCODE = '23503',
                          CONSTRAINT = 'fk_inventory_tenant_product';
            END IF;
            IF TG_TABLE_NAME = 'stock_movements' THEN
                IF product_archived AND NEW.movement_type <> 'SALE_VOID' THEN
                    RAISE EXCEPTION 'Archived product cannot receive movements'
                        USING ERRCODE = '23514',
                              CONSTRAINT = 'ck_stock_movements_product_active';
                END IF;
                IF product_unit <> NEW.unit THEN
                    RAISE EXCEPTION 'Movement unit must match product unit'
                        USING ERRCODE = '23514',
                              CONSTRAINT = 'ck_stock_movements_product_unit';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )

    op.execute(
        """
        CREATE FUNCTION validate_sale_customer()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            customer_tenant uuid;
            customer_archived boolean;
        BEGIN
            SELECT tenant_id, archived
            INTO customer_tenant, customer_archived
            FROM customers WHERE id = NEW.customer_id;
            IF NOT FOUND OR customer_tenant <> NEW.tenant_id THEN
                RAISE EXCEPTION 'Customer does not belong to sale tenant'
                    USING ERRCODE = '23503', CONSTRAINT = 'fk_sales_tenant_customer';
            END IF;
            IF customer_archived AND NEW.status <> 'VOID' THEN
                RAISE EXCEPTION 'Archived customer cannot be used for a sale'
                    USING ERRCODE = '23514', CONSTRAINT = 'ck_sales_customer_active';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER sales_validate_customer
        BEFORE INSERT OR UPDATE OF customer_id, status ON sales
        FOR EACH ROW EXECUTE FUNCTION validate_sale_customer()
        """
    )
    op.execute(
        """
        CREATE FUNCTION enforce_sale_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Sales cannot be deleted' USING ERRCODE = '55000';
            END IF;
            IF OLD.status = 'VOID' THEN
                RAISE EXCEPTION 'Voided sales are immutable' USING ERRCODE = '55000';
            END IF;
            IF OLD.status = 'POSTED' THEN
                IF NEW.status <> 'VOID'
                   OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                   OR NEW.sale_number IS DISTINCT FROM OLD.sale_number
                   OR NEW.customer_id IS DISTINCT FROM OLD.customer_id
                   OR NEW.subtotal IS DISTINCT FROM OLD.subtotal
                   OR NEW.created_at IS DISTINCT FROM OLD.created_at
                   OR NEW.created_by IS DISTINCT FROM OLD.created_by
                   OR NEW.create_idempotency_key IS DISTINCT FROM OLD.create_idempotency_key
                   OR NEW.create_request_hash IS DISTINCT FROM OLD.create_request_hash
                   OR NEW.post_idempotency_key IS DISTINCT FROM OLD.post_idempotency_key
                THEN
                    RAISE EXCEPTION 'Posted sales are immutable' USING ERRCODE = '55000';
                END IF;
            ELSIF OLD.status = 'DRAFT' AND NEW.status NOT IN ('DRAFT', 'POSTED') THEN
                RAISE EXCEPTION 'Draft sale transition is invalid' USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER sales_lifecycle_guard
        BEFORE UPDATE OR DELETE ON sales
        FOR EACH ROW EXECUTE FUNCTION enforce_sale_lifecycle()
        """
    )
    op.execute(
        """
        CREATE FUNCTION enforce_sale_item_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            parent_sale_id uuid;
            sale_tenant uuid;
            sale_status text;
            product_tenant uuid;
            product_archived boolean;
        BEGIN
            parent_sale_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.sale_id ELSE NEW.sale_id END;
            SELECT tenant_id, status INTO sale_tenant, sale_status
            FROM sales WHERE id = parent_sale_id;
            IF NOT FOUND OR sale_status <> 'DRAFT' THEN
                RAISE EXCEPTION 'Only draft sale items can change' USING ERRCODE = '55000';
            END IF;
            IF TG_OP <> 'DELETE' THEN
                SELECT tenant_id, archived INTO product_tenant, product_archived
                FROM products WHERE id = NEW.product_id;
                IF NOT FOUND OR product_tenant <> sale_tenant THEN
                    RAISE EXCEPTION 'Product does not belong to sale tenant'
                        USING ERRCODE = '23503', CONSTRAINT = 'fk_sale_items_tenant_product';
                END IF;
                IF product_archived THEN
                    RAISE EXCEPTION 'Archived product cannot be sold'
                        USING ERRCODE = '23514', CONSTRAINT = 'ck_sale_items_product_active';
                END IF;
            END IF;
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER sale_items_lifecycle_guard
        BEFORE INSERT OR UPDATE OR DELETE ON sale_items
        FOR EACH ROW EXECUTE FUNCTION enforce_sale_item_lifecycle()
        """
    )

    tenant_id = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    user_id = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"
    maintenance = "current_setting('app.internal_maintenance', true) = 'true'"
    membership_check = (
        "EXISTS (SELECT 1 FROM memberships "
        "WHERE memberships.business_id = tenant_id "
        f"AND memberships.user_id = {user_id})"
    )
    for table in ("sale_code_counters", "sales", "sale_items"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    for table in ("sale_code_counters", "sales"):
        op.execute(  # noqa: S608 -- migration table and policy names are constants.
            f"""
            CREATE POLICY {table}_tenant_access ON {table}
            FOR ALL
            USING ({maintenance} OR (tenant_id = {tenant_id} AND {membership_check}))
            WITH CHECK ({maintenance} OR (tenant_id = {tenant_id} AND {membership_check}))
            """
        )
    op.execute(
        f"""
        CREATE POLICY sale_items_tenant_access ON sale_items
        FOR ALL
        USING (
            {maintenance}
            OR (
                EXISTS (
                    SELECT 1 FROM sales
                    WHERE sales.id = sale_items.sale_id
                    AND sales.tenant_id = {tenant_id}
                    AND {membership_check}
                )
            )
        )
        WITH CHECK (
            {maintenance}
            OR (
                EXISTS (
                    SELECT 1 FROM sales
                    WHERE sales.id = sale_items.sale_id
                    AND sales.tenant_id = {tenant_id}
                    AND {membership_check}
                )
            )
        )
        """
    )

def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS sale_items_tenant_access ON sale_items")
    op.execute("DROP POLICY IF EXISTS sales_tenant_access ON sales")
    op.execute("DROP POLICY IF EXISTS sale_code_counters_tenant_access ON sale_code_counters")
    op.execute("DROP TRIGGER IF EXISTS sale_items_lifecycle_guard ON sale_items")
    op.execute("DROP FUNCTION IF EXISTS enforce_sale_item_lifecycle()")
    op.execute("DROP TRIGGER IF EXISTS sales_lifecycle_guard ON sales")
    op.execute("DROP FUNCTION IF EXISTS enforce_sale_lifecycle()")
    op.execute("DROP TRIGGER IF EXISTS sales_validate_customer ON sales")
    op.execute("DROP FUNCTION IF EXISTS validate_sale_customer()")
    op.drop_index("ix_sale_items_sale_line", table_name="sale_items")
    op.drop_table("sale_items")
    op.drop_index("ix_sales_search_number_trgm", table_name="sales")
    op.drop_index("uq_sales_tenant_void_idempotency", table_name="sales")
    op.drop_index("uq_sales_tenant_post_idempotency", table_name="sales")
    op.drop_index("ix_sales_tenant_customer_created", table_name="sales")
    op.drop_index("ix_sales_tenant_status_created", table_name="sales")
    op.drop_table("sales")
    op.drop_table("sale_code_counters")
    op.execute("ALTER TABLE stock_movements DROP CONSTRAINT ck_stock_movements_direction")
    op.execute(
        "ALTER TABLE stock_movements DROP CONSTRAINT ck_stock_movements_supported_movement_type"
    )
    op.execute(
        """
        ALTER TABLE stock_movements ADD CONSTRAINT ck_stock_movements_supported_movement_type
        CHECK (movement_type IN (
            'OPENING_STOCK', 'STOCK_RECEIPT', 'STOCK_ADJUSTMENT',
            'CUSTOMER_RETURN', 'DAMAGED', 'SPOILAGE'
        ))
        """
    )
    op.execute(
        """
        ALTER TABLE stock_movements ADD CONSTRAINT ck_stock_movements_direction
        CHECK (
            (movement_type IN ('DAMAGED', 'SPOILAGE') AND quantity < 0)
            OR (movement_type IN (
                'OPENING_STOCK', 'STOCK_RECEIPT', 'CUSTOMER_RETURN'
            ) AND quantity > 0)
            OR movement_type = 'STOCK_ADJUSTMENT'
        )
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_inventory_tenant_product()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            product_tenant uuid;
            product_unit text;
            product_archived boolean;
        BEGIN
            SELECT tenant_id, unit, archived
            INTO product_tenant, product_unit, product_archived
            FROM products WHERE id = NEW.product_id;
            IF NOT FOUND OR product_tenant <> NEW.tenant_id THEN
                RAISE EXCEPTION 'Product does not belong to inventory tenant'
                    USING ERRCODE = '23503',
                          CONSTRAINT = 'fk_inventory_tenant_product';
            END IF;
            IF TG_TABLE_NAME = 'stock_movements' THEN
                IF product_archived THEN
                    RAISE EXCEPTION 'Archived product cannot receive movements'
                        USING ERRCODE = '23514',
                              CONSTRAINT = 'ck_stock_movements_product_active';
                END IF;
                IF product_unit <> NEW.unit THEN
                    RAISE EXCEPTION 'Movement unit must match product unit'
                        USING ERRCODE = '23514',
                              CONSTRAINT = 'ck_stock_movements_product_unit';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
