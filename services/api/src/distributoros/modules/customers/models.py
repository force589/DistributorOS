from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from distributoros.db.base import Base


class CustomerCodeCounter(Base):
    __tablename__ = "customer_code_counters"

    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    next_number: Mapped[int] = mapped_column(Integer, nullable=False)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("char_length(trim(name)) > 0", name="name_not_blank"),
        UniqueConstraint(
            "tenant_id",
            "customer_code",
            name="uq_customers_tenant_customer_code",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_customers_creator_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "updated_by"],
            ["memberships.business_id", "memberships.user_id"],
            name="fk_customers_updater_membership",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_customers_tenant_archived_created",
            "tenant_id",
            "archived",
            "created_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    customer_code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    address_line_1: Mapped[str | None] = mapped_column(String(200))
    address_line_2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)
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
    "uq_customers_tenant_name_ci",
    Customer.tenant_id,
    func.lower(Customer.name),
    unique=True,
)
Index(
    "ix_customers_tenant_archived_name",
    Customer.tenant_id,
    Customer.archived,
    func.lower(Customer.name),
    Customer.id,
)
Index(
    "ix_customers_search_name_trgm",
    func.lower(Customer.name),
    postgresql_using="gin",
    postgresql_ops={"lower": "gin_trgm_ops"},
)
Index(
    "ix_customers_search_phone_trgm",
    Customer.phone,
    postgresql_using="gin",
    postgresql_ops={"phone": "gin_trgm_ops"},
)
Index(
    "ix_customers_search_email_trgm",
    func.lower(Customer.email),
    postgresql_using="gin",
    postgresql_ops={"lower": "gin_trgm_ops"},
)
Index(
    "ix_customers_search_code_trgm",
    Customer.customer_code,
    postgresql_using="gin",
    postgresql_ops={"customer_code": "gin_trgm_ops"},
)
