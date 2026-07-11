"""Add Phase 3 product management.

Revision ID: 20260628_0004
Revises: 20260628_0003
Create Date: 2026-06-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260628_0004"
down_revision: str | None = "20260628_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_code_counters",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["businesses.id"],
            name=op.f("fk_product_code_counters_tenant_id_businesses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tenant_id", name=op.f("pk_product_code_counters")),
    )
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("barcode", sa.String(length=128), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("selling_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column(
            "low_stock_threshold",
            sa.Numeric(precision=18, scale=3),
            nullable=False,
        ),
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
            name=op.f("ck_products_name_not_blank"),
        ),
        sa.CheckConstraint(
            "selling_price >= 0",
            name=op.f("ck_products_selling_price_not_negative"),
        ),
        sa.CheckConstraint(
            "low_stock_threshold >= 0",
            name=op.f("ck_products_threshold_not_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_products_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "updated_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_products_updater_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint(
            "tenant_id",
            "product_code",
            name="uq_products_tenant_product_code",
        ),
    )

    op.create_index(
        "ix_products_tenant_archived_created",
        "products",
        ["tenant_id", "archived", "created_at", "id"],
    )
    op.create_index(
        "ix_products_tenant_archived_price",
        "products",
        ["tenant_id", "archived", "selling_price", "id"],
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_products_tenant_name_ci ON products (tenant_id, lower(name))"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_products_tenant_sku_ci "
        "ON products (tenant_id, lower(sku)) WHERE sku IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_products_tenant_barcode "
        "ON products (tenant_id, barcode) WHERE barcode IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_products_tenant_archived_name "
        "ON products (tenant_id, archived, lower(name), id)"
    )
    op.execute(
        "CREATE INDEX ix_products_search_name_trgm ON products USING gin (lower(name) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_products_search_code_trgm "
        "ON products USING gin (lower(product_code) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_products_search_sku_trgm ON products USING gin (lower(sku) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_products_search_barcode_trgm ON products USING gin (barcode gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_products_search_category_trgm "
        "ON products USING gin (lower(category) gin_trgm_ops)"
    )

    tenant_id = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    user_id = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"
    maintenance = "current_setting('app.internal_maintenance', true) = 'true'"
    membership_check = (
        "EXISTS (SELECT 1 FROM memberships "
        "WHERE memberships.business_id = tenant_id "
        f"AND memberships.user_id = {user_id})"
    )
    for table in ("product_code_counters", "products"):
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(  # noqa: S608 -- table and policy names are migration constants.
            f"""
            CREATE POLICY {table}_tenant_access ON {table}
            FOR ALL
            USING ({maintenance} OR (tenant_id = {tenant_id} AND {membership_check}))
            WITH CHECK ({maintenance} OR (tenant_id = {tenant_id} AND {membership_check}))
            """
        )

def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS products_tenant_access ON products")
    op.execute("DROP POLICY IF EXISTS product_code_counters_tenant_access ON product_code_counters")
    op.drop_index("ix_products_search_category_trgm", table_name="products")
    op.drop_index("ix_products_search_barcode_trgm", table_name="products")
    op.drop_index("ix_products_search_sku_trgm", table_name="products")
    op.drop_index("ix_products_search_code_trgm", table_name="products")
    op.drop_index("ix_products_search_name_trgm", table_name="products")
    op.drop_index("ix_products_tenant_archived_name", table_name="products")
    op.drop_index("uq_products_tenant_barcode", table_name="products")
    op.drop_index("uq_products_tenant_sku_ci", table_name="products")
    op.drop_index("uq_products_tenant_name_ci", table_name="products")
    op.drop_index("ix_products_tenant_archived_price", table_name="products")
    op.drop_index("ix_products_tenant_archived_created", table_name="products")
    op.drop_table("products")
    op.drop_table("product_code_counters")
