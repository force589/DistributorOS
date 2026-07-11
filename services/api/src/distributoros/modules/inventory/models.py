from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
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


class Warehouse(Base):
    __tablename__ = "warehouses"
    __table_args__ = (
        CheckConstraint("char_length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("NOT (is_default AND archived)", name="default_not_archived"),
        UniqueConstraint("tenant_id", "id", name="uq_warehouses_tenant_id"),
        Index("ix_warehouses_tenant_archived", "tenant_id", "archived", "name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity <> 0", name="quantity_not_zero"),
        CheckConstraint(
            "movement_type IN ('OPENING_STOCK', 'STOCK_RECEIPT', "
            "'STOCK_ADJUSTMENT', 'CUSTOMER_RETURN', 'DAMAGED', 'SPOILAGE', "
            "'SALE', 'SALE_VOID')",
            name="supported_movement_type",
        ),
        CheckConstraint("char_length(trim(unit)) > 0", name="unit_not_blank"),
        CheckConstraint("char_length(request_hash) = 64", name="request_hash_length"),
        CheckConstraint(
            "(movement_type IN ('DAMAGED', 'SPOILAGE', 'SALE') AND quantity < 0) OR "
            "(movement_type IN ('OPENING_STOCK', 'STOCK_RECEIPT', 'CUSTOMER_RETURN', "
            "'SALE_VOID') "
            "AND quantity > 0) OR movement_type = 'STOCK_ADJUSTMENT'",
            name="direction",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "warehouse_id"],
            ["warehouses.tenant_id", "warehouses.id"],
            name="fk_stock_movements_tenant_warehouse",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_stock_movements_creator_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_stock_movements_tenant_idempotency"
        ),
        Index(
            "ix_stock_movements_tenant_created",
            "tenant_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_stock_movements_tenant_product_created",
            "tenant_id",
            "product_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_stock_movements_tenant_warehouse_created",
            "tenant_id",
            "warehouse_id",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(64))
    reference_id: Mapped[UUID | None] = mapped_column(Uuid)
    remarks: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class StockBalance(Base):
    __tablename__ = "stock_balances"
    __table_args__ = (
        CheckConstraint("available_quantity >= 0", name="quantity_not_negative"),
        ForeignKeyConstraint(
            ["tenant_id", "warehouse_id"],
            ["warehouses.tenant_id", "warehouses.id"],
            name="fk_stock_balances_tenant_warehouse",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_stock_balances_tenant_warehouse_quantity",
            "tenant_id",
            "warehouse_id",
            "available_quantity",
            "product_id",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    product_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("products.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    warehouse_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    available_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


Index(
    "uq_warehouses_tenant_name_ci",
    Warehouse.tenant_id,
    func.lower(Warehouse.name),
    unique=True,
)
Index(
    "uq_warehouses_one_default",
    Warehouse.tenant_id,
    unique=True,
    postgresql_where=Warehouse.is_default.is_(True),
)
Index(
    "uq_stock_movements_opening_stock",
    StockMovement.tenant_id,
    StockMovement.product_id,
    StockMovement.warehouse_id,
    unique=True,
    postgresql_where=StockMovement.movement_type == "OPENING_STOCK",
)
