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


class ProductCodeCounter(Base):
    __tablename__ = "product_code_counters"

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    next_number: Mapped[int] = mapped_column(Integer, nullable=False)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("char_length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("selling_price >= 0", name="selling_price_not_negative"),
        CheckConstraint("low_stock_threshold >= 0", name="threshold_not_negative"),
        UniqueConstraint(
            "tenant_id",
            "product_code",
            name="uq_products_tenant_product_code",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_products_creator_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "updated_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_products_updater_membership",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_products_tenant_archived_created",
            "tenant_id",
            "archived",
            "created_at",
            "id",
        ),
        Index(
            "ix_products_tenant_archived_price",
            "tenant_id",
            "archived",
            "selling_price",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    product_code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100))
    barcode: Mapped[str | None] = mapped_column(String(128))
    category: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    low_stock_threshold: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    updated_by: Mapped[UUID] = mapped_column(Uuid, nullable=False)


Index(
    "uq_products_tenant_name_ci",
    Product.tenant_id,
    func.lower(Product.name),
    unique=True,
)
Index(
    "uq_products_tenant_sku_ci",
    Product.tenant_id,
    func.lower(Product.sku),
    unique=True,
    postgresql_where=Product.sku.is_not(None),
)
Index(
    "uq_products_tenant_barcode",
    Product.tenant_id,
    Product.barcode,
    unique=True,
    postgresql_where=Product.barcode.is_not(None),
)
Index(
    "ix_products_tenant_archived_name",
    Product.tenant_id,
    Product.archived,
    func.lower(Product.name),
    Product.id,
)
Index(
    "ix_products_search_name_trgm",
    func.lower(Product.name),
    postgresql_using="gin",
    postgresql_ops={"lower": "gin_trgm_ops"},
)
Index(
    "ix_products_search_code_trgm",
    func.lower(Product.product_code),
    postgresql_using="gin",
    postgresql_ops={"lower": "gin_trgm_ops"},
)
Index(
    "ix_products_search_sku_trgm",
    func.lower(Product.sku),
    postgresql_using="gin",
    postgresql_ops={"lower": "gin_trgm_ops"},
)
Index(
    "ix_products_search_barcode_trgm",
    Product.barcode,
    postgresql_using="gin",
    postgresql_ops={"barcode": "gin_trgm_ops"},
)
Index(
    "ix_products_search_category_trgm",
    func.lower(Product.category),
    postgresql_using="gin",
    postgresql_ops={"lower": "gin_trgm_ops"},
)
