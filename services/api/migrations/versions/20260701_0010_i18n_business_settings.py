"""Add Phase 8.5 business preferences and multi-currency invoices.

Revision ID: 20260701_0010
Revises: 20260630_0009
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_0010"
down_revision: str | None = "20260630_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column("currency", sa.String(length=3), server_default="INR", nullable=False),
    )
    op.add_column(
        "businesses",
        sa.Column("language", sa.String(length=8), server_default="en", nullable=False),
    )
    op.add_column(
        "businesses",
        sa.Column("theme", sa.String(length=16), server_default="system", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_businesses_supported_currency"),
        "businesses",
        "currency IN ('INR', 'USD', 'EUR', 'GBP', 'AED', 'SAR', 'SGD', 'MYR')",
    )
    op.create_check_constraint(
        op.f("ck_businesses_supported_language"),
        "businesses",
        "language IN ('en', 'ml')",
    )
    op.create_check_constraint(
        op.f("ck_businesses_supported_theme"),
        "businesses",
        "theme IN ('light', 'dark', 'system')",
    )
    op.drop_constraint(op.f("ck_invoices_supported_currency"), "invoices", type_="check")
    op.create_check_constraint(
        op.f("ck_invoices_supported_currency"),
        "invoices",
        "currency IN ('INR', 'USD', 'EUR', 'GBP', 'AED', 'SAR', 'SGD', 'MYR')",
    )

    tenant_id = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
    user_id = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"
    op.execute(
        f"""
        CREATE POLICY businesses_update ON businesses
        FOR UPDATE TO distributoros_app
        USING (
            id = {tenant_id}
            AND EXISTS (
                SELECT 1 FROM memberships
                WHERE memberships.business_id = businesses.id
                AND memberships.user_id = {user_id}
            )
        )
        WITH CHECK (id = {tenant_id})
        """
    )
    op.execute(
        "GRANT UPDATE (business_name, currency, language, theme) ON businesses TO distributoros_app"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE UPDATE (business_name, currency, language, theme) "
        "ON businesses FROM distributoros_app"
    )
    op.execute("DROP POLICY IF EXISTS businesses_update ON businesses")
    op.drop_constraint(op.f("ck_invoices_supported_currency"), "invoices", type_="check")
    op.create_check_constraint(
        op.f("ck_invoices_supported_currency"), "invoices", "currency = 'INR'"
    )
    op.drop_constraint(op.f("ck_businesses_supported_theme"), "businesses", type_="check")
    op.drop_constraint(op.f("ck_businesses_supported_language"), "businesses", type_="check")
    op.drop_constraint(op.f("ck_businesses_supported_currency"), "businesses", type_="check")
    op.drop_column("businesses", "theme")
    op.drop_column("businesses", "language")
    op.drop_column("businesses", "currency")
