from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from distributoros.db.base import Base


class CustomerLedgerEntry(Base):
    __tablename__ = "customer_ledger_entries"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('SALE', 'REVERSAL', 'PAYMENT', 'PAYMENT_REVERSAL')",
            name="supported_entry_type",
        ),
        CheckConstraint(
            "reference_type IN ('SALE', 'PAYMENT')",
            name="supported_reference_type",
        ),
        CheckConstraint("debit >= 0 AND credit >= 0", name="amounts_not_negative"),
        CheckConstraint(
            "(entry_type = 'SALE' AND debit > 0 AND credit = 0) OR "
            "(entry_type = 'REVERSAL' AND debit = 0 AND credit > 0) OR "
            "(entry_type = 'PAYMENT' AND debit = 0 AND credit > 0) OR "
            "(entry_type = 'PAYMENT_REVERSAL' AND debit > 0 AND credit = 0)",
            name="entry_direction",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_ledger_creator_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "entry_type",
            "reference_type",
            "reference_id",
            name="uq_ledger_tenant_type_reference",
        ),
        Index(
            "ix_ledger_tenant_customer_created",
            "tenant_id",
            "customer_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_ledger_tenant_type_created",
            "tenant_id",
            "entry_type",
            "created_at",
            "id",
        ),
        Index(
            "ix_ledger_tenant_reference",
            "tenant_id",
            "reference_type",
            "reference_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    debit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)


class CustomerBalanceProjection(Base):
    __tablename__ = "customer_balance_projections"
    __table_args__ = (
        CheckConstraint("outstanding_balance >= 0", name="outstanding_not_negative"),
        CheckConstraint("available_credit >= 0", name="available_credit_not_negative"),
        CheckConstraint(
            "NOT (outstanding_balance > 0 AND available_credit > 0)",
            name="balance_or_credit_not_both",
        ),
        CheckConstraint("total_sales >= 0", name="total_sales_not_negative"),
        CheckConstraint("total_payments >= 0", name="total_payments_not_negative"),
        Index(
            "ix_customer_balances_tenant_outstanding",
            "tenant_id",
            "outstanding_balance",
            "customer_id",
        ),
        Index(
            "ix_customer_balances_tenant_credit",
            "tenant_id",
            "available_credit",
            "customer_id",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    outstanding_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    available_credit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_sales: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_payments: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    last_sale_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_payment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
