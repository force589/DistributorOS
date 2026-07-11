"""Add Phase 4 immutable inventory management.

Revision ID: 20260628_0005
Revises: 20260628_0004
Create Date: 2026-06-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260628_0005"
down_revision: str | None = "20260628_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "warehouses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("archived", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(trim(name)) > 0", name=op.f("ck_warehouses_name_not_blank")
        ),
        sa.CheckConstraint(
            "NOT (is_default AND archived)",
            name=op.f("ck_warehouses_default_not_archived"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_warehouses_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouses")),
        sa.UniqueConstraint("tenant_id", "id", name="uq_warehouses_tenant_id"),
    )
    op.create_index(
        "ix_warehouses_tenant_archived",
        "warehouses",
        ["tenant_id", "archived", "name"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_warehouses_tenant_name_ci ON warehouses (tenant_id, lower(name))"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_warehouses_one_default ON warehouses (tenant_id) WHERE is_default"
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint("quantity <> 0", name=op.f("ck_stock_movements_quantity_not_zero")),
        sa.CheckConstraint(
            "movement_type IN ('OPENING_STOCK', 'STOCK_RECEIPT', "
            "'STOCK_ADJUSTMENT', 'CUSTOMER_RETURN', 'DAMAGED', 'SPOILAGE')",
            name=op.f("ck_stock_movements_supported_movement_type"),
        ),
        sa.CheckConstraint(
            "char_length(trim(unit)) > 0",
            name=op.f("ck_stock_movements_unit_not_blank"),
        ),
        sa.CheckConstraint(
            "char_length(request_hash) = 64",
            name=op.f("ck_stock_movements_request_hash_length"),
        ),
        sa.CheckConstraint(
            "(movement_type IN ('DAMAGED', 'SPOILAGE') AND quantity < 0) OR "
            "(movement_type IN ('OPENING_STOCK', 'STOCK_RECEIPT', 'CUSTOMER_RETURN') "
            "AND quantity > 0) OR movement_type = 'STOCK_ADJUSTMENT'",
            name=op.f("ck_stock_movements_direction"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_stock_movements_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_stock_movements_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "warehouse_id"],
            ["warehouses.tenant_id", "warehouses.id"],
            name="fk_stock_movements_tenant_warehouse",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_stock_movements_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movements")),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_stock_movements_tenant_idempotency",
        ),
    )
    op.create_index(
        "ix_stock_movements_tenant_created",
        "stock_movements",
        ["tenant_id", "created_at", "id"],
    )
    op.create_index(
        "ix_stock_movements_tenant_product_created",
        "stock_movements",
        ["tenant_id", "product_id", "created_at", "id"],
    )
    op.create_index(
        "ix_stock_movements_tenant_warehouse_created",
        "stock_movements",
        ["tenant_id", "warehouse_id", "created_at", "id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_stock_movements_opening_stock "
        "ON stock_movements (tenant_id, product_id, warehouse_id) "
        "WHERE movement_type = 'OPENING_STOCK'"
    )

    op.create_table(
        "stock_balances",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("available_quantity", sa.Numeric(precision=20, scale=3), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "available_quantity >= 0",
            name=op.f("ck_stock_balances_quantity_not_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_stock_balances_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "warehouse_id"],
            ["warehouses.tenant_id", "warehouses.id"],
            name="fk_stock_balances_tenant_warehouse",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "tenant_id", "product_id", "warehouse_id", name=op.f("pk_stock_balances")
        ),
    )
    op.create_index(
        "ix_stock_balances_tenant_warehouse_quantity",
        "stock_balances",
        ["tenant_id", "warehouse_id", "available_quantity", "product_id"],
    )

    op.execute(
        """
        INSERT INTO warehouses (id, tenant_id, name, is_default, archived, created_at)
        SELECT gen_random_uuid(), id, 'Main Warehouse', true, false, now()
        FROM businesses
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        CREATE FUNCTION create_business_default_warehouse()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        BEGIN
            INSERT INTO warehouses (
                id, tenant_id, name, is_default, archived, created_at
            ) VALUES (
                gen_random_uuid(), NEW.id, 'Main Warehouse', true, false, now()
            );
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER businesses_create_default_warehouse
        AFTER INSERT ON businesses
        FOR EACH ROW EXECUTE FUNCTION create_business_default_warehouse()
        """
    )

    op.execute(
        """
        CREATE FUNCTION validate_inventory_tenant_product()
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
    for table in ("stock_movements", "stock_balances"):
        op.execute(
            f"""
            CREATE TRIGGER {table}_validate_tenant_product
            BEFORE INSERT OR UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION validate_inventory_tenant_product()
            """  # noqa: S608 -- table names are migration constants.
        )

    op.execute(
        """
        CREATE FUNCTION prevent_stock_movement_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'Stock movements are immutable'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER stock_movements_immutable
        BEFORE UPDATE OR DELETE ON stock_movements
        FOR EACH ROW EXECUTE FUNCTION prevent_stock_movement_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION prevent_product_unit_change_with_stock()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.unit IS DISTINCT FROM OLD.unit
               AND EXISTS (
                   SELECT 1 FROM stock_movements WHERE product_id = OLD.id LIMIT 1
               ) THEN
                RAISE EXCEPTION 'Product unit cannot change after stock is recorded'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_products_inventory_unit_locked';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER products_lock_inventory_unit
        BEFORE UPDATE OF unit ON products
        FOR EACH ROW EXECUTE FUNCTION prevent_product_unit_change_with_stock()
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
    for table in ("warehouses", "stock_movements", "stock_balances"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')

    op.execute(
        f"""
        CREATE POLICY warehouses_select_update ON warehouses
        FOR ALL
        USING ({maintenance} OR (tenant_id = {tenant_id} AND {membership_check}))
        WITH CHECK ({maintenance} OR tenant_id = {tenant_id})
        """
    )
    for table in ("stock_movements", "stock_balances"):
        op.execute(  # noqa: S608 -- table and policy names are migration constants.
            f"""
            CREATE POLICY {table}_tenant_access ON {table}
            FOR ALL
            USING ({maintenance} OR (tenant_id = {tenant_id} AND {membership_check}))
            WITH CHECK ({maintenance} OR (tenant_id = {tenant_id} AND {membership_check}))
            """
        )

def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS products_lock_inventory_unit ON products")
    op.execute("DROP FUNCTION IF EXISTS prevent_product_unit_change_with_stock()")
    op.execute("DROP TRIGGER IF EXISTS stock_movements_immutable ON stock_movements")
    op.execute("DROP FUNCTION IF EXISTS prevent_stock_movement_mutation()")
    for table in ("stock_balances", "stock_movements"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_validate_tenant_product ON {table}")
    op.execute("DROP FUNCTION IF EXISTS validate_inventory_tenant_product()")
    op.execute("DROP TRIGGER IF EXISTS businesses_create_default_warehouse ON businesses")
    op.execute("DROP FUNCTION IF EXISTS create_business_default_warehouse()")
    op.execute("DROP POLICY IF EXISTS stock_balances_tenant_access ON stock_balances")
    op.execute("DROP POLICY IF EXISTS stock_movements_tenant_access ON stock_movements")
    op.execute("DROP POLICY IF EXISTS warehouses_select_update ON warehouses")
    op.drop_index("ix_stock_balances_tenant_warehouse_quantity", table_name="stock_balances")
    op.drop_table("stock_balances")
    op.drop_index("uq_stock_movements_opening_stock", table_name="stock_movements")
    op.drop_index("ix_stock_movements_tenant_warehouse_created", table_name="stock_movements")
    op.drop_index("ix_stock_movements_tenant_product_created", table_name="stock_movements")
    op.drop_index("ix_stock_movements_tenant_created", table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_index("uq_warehouses_one_default", table_name="warehouses")
    op.drop_index("uq_warehouses_tenant_name_ci", table_name="warehouses")
    op.drop_index("ix_warehouses_tenant_archived", table_name="warehouses")
    op.drop_table("warehouses")
