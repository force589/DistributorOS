from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
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


class SaleCodeCounter(Base):
    __tablename__ = "sale_code_counters"

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    next_number: Mapped[int] = mapped_column(Integer, nullable=False)


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'POSTED', 'VOID')", name="supported_status"),
        CheckConstraint("subtotal > 0", name="subtotal_positive"),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_sales_creator_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "sale_number", name="uq_sales_tenant_sale_number"),
        UniqueConstraint(
            "tenant_id",
            "create_idempotency_key",
            name="uq_sales_tenant_create_idempotency",
        ),
        Index("ix_sales_tenant_status_created", "tenant_id", "status", "created_at", "id"),
        Index("ix_sales_tenant_customer_created", "tenant_id", "customer_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    sale_number: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    create_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    create_request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    post_idempotency_key: Mapped[str | None] = mapped_column(String(128))
    void_idempotency_key: Mapped[str | None] = mapped_column(String(128))


class SaleItem(Base):
    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint("line_number > 0", name="line_number_positive"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price > 0", name="unit_price_positive"),
        CheckConstraint("line_total > 0", name="line_total_positive"),
        CheckConstraint(
            "line_total = round(quantity * unit_price, 2)",
            name="line_total_calculated",
        ),
        CheckConstraint(
            "char_length(trim(product_name_snapshot)) > 0",
            name="product_snapshot_not_blank",
        ),
        CheckConstraint(
            "char_length(trim(unit_snapshot)) > 0",
            name="unit_snapshot_not_blank",
        ),
        UniqueConstraint("sale_id", "product_id", name="uq_sale_items_sale_product"),
        UniqueConstraint("sale_id", "line_number", name="uq_sale_items_sale_line_number"),
        Index("ix_sale_items_sale_line", "sale_id", "line_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    sale_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    unit_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


Index(
    "uq_sales_tenant_post_idempotency",
    Sale.tenant_id,
    Sale.post_idempotency_key,
    unique=True,
    postgresql_where=Sale.post_idempotency_key.is_not(None),
)
Index(
    "uq_sales_tenant_void_idempotency",
    Sale.tenant_id,
    Sale.void_idempotency_key,
    unique=True,
    postgresql_where=Sale.void_idempotency_key.is_not(None),
)
Index(
    "ix_sales_search_number_trgm",
    func.lower(Sale.sale_number),
    postgresql_using="gin",
    postgresql_ops={"lower": "gin_trgm_ops"},
)
