from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from distributoros.db.base import Base


class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = (
        CheckConstraint("char_length(trim(business_name)) > 0", name="business_name_not_blank"),
        CheckConstraint(
            "currency IN ('INR', 'USD', 'EUR', 'GBP', 'AED', 'SAR', 'SGD', 'MYR')",
            name="supported_currency",
        ),
        CheckConstraint("language IN ('en', 'ml')", name="supported_language"),
        CheckConstraint("theme IN ('light', 'dark', 'system')", name="supported_theme"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    business_name: Mapped[str] = mapped_column(String(120), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="INR", server_default="INR"
    )
    language: Mapped[str] = mapped_column(
        String(8), nullable=False, default="en", server_default="en"
    )
    theme: Mapped[str] = mapped_column(
        String(16), nullable=False, default="system", server_default="system"
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Kolkata", server_default="Asia/Kolkata"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (CheckConstraint("role IN ('owner')", name="supported_role"),)

    business_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="owner")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
