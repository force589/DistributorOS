"""Make customer-name uniqueness case-insensitive.

Revision ID: 20260628_0003
Revises: 20260628_0002
Create Date: 2026-06-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260628_0003"
down_revision: str | None = "20260628_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_customers_tenant_name", "customers", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX uq_customers_tenant_name_ci ON customers (tenant_id, lower(name))"
    )


def downgrade() -> None:
    op.drop_index("uq_customers_tenant_name_ci", table_name="customers")
    op.create_unique_constraint("uq_customers_tenant_name", "customers", ["tenant_id", "name"])
