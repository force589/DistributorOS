from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from distributoros.db.base import Base


class PaymentNumberCounter(Base):
    __tablename__ = "payment_number_counters"

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    next_number: Mapped[int] = mapped_column(Integer, nullable=False)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(
            "payment_method IN ('cash', 'upi', 'bank_transfer', 'cheque', 'other')",
            name="supported_payment_method",
        ),
        CheckConstraint("status IN ('POSTED', 'VOID')", name="supported_status"),
        CheckConstraint(
            "char_length(trim(payment_number)) > 0",
            name="payment_number_not_blank",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_payments_creator_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "payment_number",
            name="uq_payments_tenant_payment_number",
        ),
        UniqueConstraint(
            "tenant_id",
            "create_idempotency_key",
            name="uq_payments_tenant_create_idempotency",
        ),
        Index(
            "ix_payments_tenant_status_created",
            "tenant_id",
            "status",
            "created_at",
            "id",
        ),
        Index(
            "ix_payments_tenant_customer_created",
            "tenant_id",
            "customer_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_payments_tenant_method_created",
            "tenant_id",
            "payment_method",
            "created_at",
            "id",
        ),
        Index(
            "ix_payments_tenant_payment_date",
            "tenant_id",
            "payment_date",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    payment_number: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="POSTED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    create_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    create_request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    void_idempotency_key: Mapped[str | None] = mapped_column(String(128))


Index(
    "uq_payments_tenant_void_idempotency",
    Payment.tenant_id,
    Payment.void_idempotency_key,
    unique=True,
    postgresql_where=Payment.void_idempotency_key.is_not(None),
)
Index(
    "ix_payments_search_number_trgm",
    func.lower(Payment.payment_number),
    postgresql_using="gin",
    postgresql_ops={"lower": "gin_trgm_ops"},
)
Index(
    "ix_payments_search_reference_trgm",
    func.lower(Payment.reference_number),
    postgresql_using="gin",
    postgresql_ops={"lower": "gin_trgm_ops"},
    postgresql_where=Payment.reference_number.is_not(None),
)


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        CheckConstraint("allocated_amount > 0", name="allocated_amount_positive"),
        UniqueConstraint(
            "tenant_id",
            "payment_id",
            "ledger_entry_id",
            name="uq_payment_allocations_payment_ledger",
        ),
        Index(
            "ix_payment_allocations_tenant_payment",
            "tenant_id",
            "payment_id",
            "created_at",
        ),
        Index(
            "ix_payment_allocations_tenant_ledger",
            "tenant_id",
            "ledger_entry_id",
            "created_at",
        ),
        Index(
            "ix_payment_allocations_tenant_invoice",
            "tenant_id",
            "invoice_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    payment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False
    )
    ledger_entry_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("customer_ledger_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    invoice_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("invoices.id", ondelete="RESTRICT"),
    )
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


Index(
    "uq_payment_allocations_payment_invoice",
    PaymentAllocation.tenant_id,
    PaymentAllocation.payment_id,
    PaymentAllocation.invoice_id,
    unique=True,
    postgresql_where=PaymentAllocation.invoice_id.is_not(None),
)
