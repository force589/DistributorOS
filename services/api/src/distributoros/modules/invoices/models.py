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
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from distributoros.db.base import Base


class InvoiceNumberCounter(Base):
    __tablename__ = "invoice_number_counters"

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    next_number: Mapped[int] = mapped_column(Integer, nullable=False)


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'ISSUED', 'VOID')", name="supported_status"),
        CheckConstraint(
            "currency IN ('INR', 'USD', 'EUR', 'GBP', 'AED', 'SAR', 'SGD', 'MYR')",
            name="supported_currency",
        ),
        CheckConstraint("subtotal > 0", name="subtotal_positive"),
        CheckConstraint("tax_total >= 0", name="tax_total_not_negative"),
        CheckConstraint("grand_total = subtotal + tax_total", name="grand_total_calculated"),
        CheckConstraint(
            "char_length(trim(invoice_number)) > 0",
            name="invoice_number_not_blank",
        ),
        CheckConstraint(
            "char_length(trim(customer_name_snapshot)) > 0",
            name="customer_snapshot_not_blank",
        ),
        CheckConstraint(
            "char_length(trim(sale_number_snapshot)) > 0",
            name="sale_number_snapshot_not_blank",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_invoices_creator_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "invoice_number",
            name="uq_invoices_tenant_invoice_number",
        ),
        UniqueConstraint("tenant_id", "sale_id", name="uq_invoices_tenant_sale"),
        UniqueConstraint(
            "tenant_id",
            "create_idempotency_key",
            name="uq_invoices_tenant_create_idempotency",
        ),
        Index("ix_invoices_tenant_status_created", "tenant_id", "status", "created_at", "id"),
        Index(
            "ix_invoices_tenant_customer_created",
            "tenant_id",
            "customer_id",
            "created_at",
            "id",
        ),
        Index("ix_invoices_tenant_issue_date", "tenant_id", "issue_date", "created_at", "id"),
        Index("ix_invoices_tenant_sale", "tenant_id", "sale_id"),
        Index("ix_invoices_tenant_ledger", "tenant_id", "ledger_entry_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    invoice_number: Mapped[str] = mapped_column(String(32), nullable=False)
    sale_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False
    )
    ledger_entry_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("customer_ledger_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    pdf_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sale_number_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    customer_phone_snapshot: Mapped[str | None] = mapped_column(String(32))
    customer_address_line_1_snapshot: Mapped[str | None] = mapped_column(String(200))
    customer_address_line_2_snapshot: Mapped[str | None] = mapped_column(String(200))
    customer_city_snapshot: Mapped[str | None] = mapped_column(String(100))
    customer_state_snapshot: Mapped[str | None] = mapped_column(String(100))
    customer_postal_code_snapshot: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    create_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    create_request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    issue_idempotency_key: Mapped[str | None] = mapped_column(String(128))
    void_idempotency_key: Mapped[str | None] = mapped_column(String(128))


Index(
    "uq_invoices_tenant_issue_idempotency",
    Invoice.tenant_id,
    Invoice.issue_idempotency_key,
    unique=True,
    postgresql_where=Invoice.issue_idempotency_key.is_not(None),
)
Index(
    "uq_invoices_tenant_void_idempotency",
    Invoice.tenant_id,
    Invoice.void_idempotency_key,
    unique=True,
    postgresql_where=Invoice.void_idempotency_key.is_not(None),
)
Index(
    "ix_invoices_search_number_trgm",
    func.lower(Invoice.invoice_number),
    postgresql_using="gin",
    postgresql_ops={"lower": "gin_trgm_ops"},
)
Index(
    "ix_invoices_search_customer_trgm",
    func.lower(Invoice.customer_name_snapshot),
    postgresql_using="gin",
    postgresql_ops={"lower": "gin_trgm_ops"},
)
Index(
    "ix_invoices_search_sale_trgm",
    func.lower(Invoice.sale_number_snapshot),
    postgresql_using="gin",
    postgresql_ops={"lower": "gin_trgm_ops"},
)


class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    __table_args__ = (
        CheckConstraint("line_number > 0", name="line_number_positive"),
        CheckConstraint("quantity_snapshot > 0", name="quantity_positive"),
        CheckConstraint("unit_price_snapshot > 0", name="unit_price_positive"),
        CheckConstraint("line_total > 0", name="line_total_positive"),
        CheckConstraint(
            "line_total = round(quantity_snapshot * unit_price_snapshot, 2)",
            name="line_total_calculated",
        ),
        CheckConstraint(
            "char_length(trim(product_snapshot)) > 0",
            name="product_snapshot_not_blank",
        ),
        CheckConstraint(
            "char_length(trim(unit_snapshot)) > 0",
            name="unit_snapshot_not_blank",
        ),
        UniqueConstraint("invoice_id", "line_number", name="uq_invoice_items_invoice_line"),
        Index("ix_invoice_items_tenant_invoice_line", "tenant_id", "invoice_id", "line_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    invoice_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    product_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    unit_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity_snapshot: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
