from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

PaymentMethod = Literal["cash", "upi", "bank_transfer", "cheque", "other"]
PaymentStatus = Literal["POSTED", "VOID"]
PaymentStatusFilter = Literal["all", "posted", "void"]
PaymentMethodFilter = Literal["all", "cash", "upi", "bank_transfer", "cheque", "other"]
PaymentSort = Literal["newest", "oldest"]

PAYMENT_AMOUNT_MAX = Decimal("9999999999999999.99")


def _positive_money(value: object, *, field_name: str, label: str) -> Decimal:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise PydanticCustomError(f"payment_{field_name}_required", f"{label} is required.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PydanticCustomError(
            f"payment_{field_name}_invalid", f"Enter a valid {label.lower()}."
        ) from exc
    if not number.is_finite():
        raise PydanticCustomError(
            f"payment_{field_name}_invalid", f"Enter a valid {label.lower()}."
        )
    if number <= 0:
        raise PydanticCustomError(
            f"payment_{field_name}_positive", f"{label} must be greater than zero."
        )
    if number > PAYMENT_AMOUNT_MAX:
        raise PydanticCustomError(
            f"payment_{field_name}_too_large",
            f"{label} is too large. Enter a smaller value.",
        )
    exponent = number.as_tuple().exponent
    if isinstance(exponent, int) and max(-exponent, 0) > 2:
        raise PydanticCustomError(
            f"payment_{field_name}_precision",
            f"{label} can have at most 2 decimal places.",
        )
    return number.quantize(Decimal("0.01"))


def _optional_text(value: str | None, *, max_length: int, label: str) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > max_length:
        raise PydanticCustomError(
            "payment_text_too_long",
            f"{label} must be {max_length} characters or fewer.",
        )
    return stripped


class PaymentAllocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ledger_entry_id: UUID | None = None
    invoice_id: UUID | None = None
    allocated_amount: Decimal

    @model_validator(mode="after")
    def require_one_target(self) -> "PaymentAllocationRequest":
        if (self.ledger_entry_id is None) == (self.invoice_id is None):
            raise PydanticCustomError(
                "payment_allocation_target_required",
                "Select exactly one invoice or legacy ledger entry for this allocation.",
            )
        return self

    @field_validator("allocated_amount", mode="before")
    @classmethod
    def validate_allocated_amount(cls, value: object) -> Decimal:
        return _positive_money(value, field_name="allocation_amount", label="Allocation amount")


class PaymentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    payment_date: date
    amount: Decimal
    payment_method: PaymentMethod
    reference_number: str | None = None
    notes: str | None = None
    allocations: list[PaymentAllocationRequest] = Field(default_factory=list, max_length=100)

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: object) -> Decimal:
        return _positive_money(value, field_name="amount", label="Payment amount")

    @field_validator("reference_number")
    @classmethod
    def validate_reference_number(cls, value: str | None) -> str | None:
        return _optional_text(value, max_length=120, label="Reference number")

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        return _optional_text(value, max_length=1000, label="Notes")


class PaymentAllocationResponse(BaseModel):
    id: UUID
    ledger_entry_id: UUID
    invoice_id: UUID | None = None
    reference_type: str
    reference: str
    allocated_amount: Decimal
    created_at: datetime


class PaymentResponse(BaseModel):
    id: UUID
    payment_number: str
    customer_id: UUID
    customer_name: str
    payment_date: date
    amount: Decimal
    payment_method: PaymentMethod
    reference_number: str | None
    notes: str | None
    status: PaymentStatus
    created_at: datetime
    created_by: UUID
    allocated_amount: Decimal
    unallocated_amount: Decimal
    allocations: list[PaymentAllocationResponse]


class PaymentListItemResponse(BaseModel):
    id: UUID
    payment_number: str
    customer_id: UUID
    customer_name: str
    payment_date: date
    amount: Decimal
    payment_method: PaymentMethod
    reference_number: str | None
    status: PaymentStatus
    created_at: datetime
    allocated_amount: Decimal
    unallocated_amount: Decimal


class PaymentListResponse(BaseModel):
    items: list[PaymentListItemResponse]
    next_cursor: str | None
    has_more: bool
    page_size: int


class PaymentMutationResponse(BaseModel):
    payment: PaymentResponse
    message: str


class CustomerCreditResponse(BaseModel):
    customer_id: UUID
    available_credit: Decimal


class CustomerBalanceResponse(BaseModel):
    customer_id: UUID
    outstanding_balance: Decimal
    available_credit: Decimal
    total_sales: Decimal
    total_payments: Decimal
    last_sale_date: datetime | None
    last_payment_date: datetime | None
