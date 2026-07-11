from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

SaleStatus = Literal["DRAFT", "POSTED", "VOID"]
SaleStatusFilter = Literal["all", "draft", "posted", "void"]
SaleSort = Literal["newest", "oldest"]

QUANTITY_MAX = Decimal("99999999999999999.999")
PRICE_MAX = Decimal("999999999999.99")


def _positive_decimal(
    value: object,
    *,
    field_name: str,
    label: str,
    decimal_places: int,
    max_value: Decimal,
) -> Decimal:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise PydanticCustomError(f"sale_{field_name}_required", f"{label} is required.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PydanticCustomError(
            f"sale_{field_name}_invalid", f"Enter a valid {label.lower()}."
        ) from exc
    if not number.is_finite():
        raise PydanticCustomError(f"sale_{field_name}_invalid", f"Enter a valid {label.lower()}.")
    if number <= 0:
        raise PydanticCustomError(
            f"sale_{field_name}_positive", f"{label} must be greater than zero."
        )
    if number > max_value:
        raise PydanticCustomError(
            f"sale_{field_name}_too_large", f"{label} is too large. Enter a smaller value."
        )
    exponent = number.as_tuple().exponent
    if isinstance(exponent, int) and max(-exponent, 0) > decimal_places:
        raise PydanticCustomError(
            f"sale_{field_name}_precision",
            f"{label} can have at most {decimal_places} decimal places.",
        )
    return number.quantize(Decimal(1).scaleb(-decimal_places))


class SaleItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    quantity: Decimal
    unit_price: Decimal

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, value: object) -> Decimal:
        return _positive_decimal(
            value,
            field_name="quantity",
            label="Quantity",
            decimal_places=3,
            max_value=QUANTITY_MAX,
        )

    @field_validator("unit_price", mode="before")
    @classmethod
    def validate_unit_price(cls, value: object) -> Decimal:
        return _positive_decimal(
            value,
            field_name="unit_price",
            label="Unit price",
            decimal_places=2,
            max_value=PRICE_MAX,
        )


class SaleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    items: list[SaleItemRequest] = Field(min_length=1, max_length=100)


class SaleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID | None = None
    items: list[SaleItemRequest] | None = Field(default=None, min_length=1, max_length=100)
    expected_updated_at: datetime | None = None


class SaleItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    product_name_snapshot: str
    unit_snapshot: str
    created_at: datetime


class SaleListItemResponse(BaseModel):
    id: UUID
    sale_number: str
    customer_id: UUID
    customer_name: str
    status: SaleStatus
    subtotal: Decimal
    item_count: int
    created_at: datetime
    updated_at: datetime


class SaleResponse(BaseModel):
    id: UUID
    sale_number: str
    customer_id: UUID
    customer_name: str
    status: SaleStatus
    subtotal: Decimal
    created_at: datetime
    created_by: UUID
    updated_at: datetime
    items: list[SaleItemResponse]


class SaleListResponse(BaseModel):
    items: list[SaleListItemResponse]
    next_cursor: str | None
    has_more: bool
    page_size: int


class SaleMutationResponse(BaseModel):
    sale: SaleResponse
    message: str
