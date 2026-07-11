from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic_core import PydanticCustomError

MovementType = Literal[
    "OPENING_STOCK",
    "STOCK_RECEIPT",
    "STOCK_ADJUSTMENT",
    "CUSTOMER_RETURN",
    "DAMAGED",
    "SPOILAGE",
    "SALE",
    "SALE_VOID",
]
LowStockStatus = Literal["OUT_OF_STOCK", "LOW_STOCK", "NORMAL"]

QUANTITY_MAX = Decimal("99999999999999999.999")
REMARKS_MAX_LENGTH = 1000


def _quantity(value: object, *, allow_negative: bool) -> Decimal:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise PydanticCustomError("inventory_quantity_required", "Quantity is required.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PydanticCustomError("inventory_quantity_invalid", "Enter a valid quantity.") from exc
    if not number.is_finite():
        raise PydanticCustomError("inventory_quantity_invalid", "Enter a valid quantity.")
    if number == 0:
        raise PydanticCustomError("inventory_quantity_zero", "Quantity must not be zero.")
    if not allow_negative and number < 0:
        raise PydanticCustomError(
            "inventory_quantity_positive", "Quantity must be greater than zero."
        )
    if abs(number) > QUANTITY_MAX:
        raise PydanticCustomError(
            "inventory_quantity_too_large", "Quantity is too large. Enter a smaller value."
        )
    exponent = number.as_tuple().exponent
    if isinstance(exponent, int) and max(-exponent, 0) > 3:
        raise PydanticCustomError(
            "inventory_quantity_precision", "Quantity can have at most 3 decimal places."
        )
    return number.quantize(Decimal("0.001"))


def _remarks(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PydanticCustomError("inventory_remarks_invalid", "Remarks must be text.")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > REMARKS_MAX_LENGTH:
        raise PydanticCustomError(
            "inventory_remarks_too_long",
            f"Remarks must not exceed {REMARKS_MAX_LENGTH} characters.",
        )
    return normalized


class PositiveStockRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    warehouse_id: UUID | None = None
    quantity: Decimal
    remarks: str | None = None

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, value: object) -> Decimal:
        return _quantity(value, allow_negative=False)

    @field_validator("remarks", mode="before")
    @classmethod
    def validate_remarks(cls, value: object) -> str | None:
        return _remarks(value)


class AdjustmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    warehouse_id: UUID | None = None
    quantity: Decimal
    reason: str

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, value: object) -> Decimal:
        return _quantity(value, allow_negative=True)

    @field_validator("reason", mode="before")
    @classmethod
    def validate_reason(cls, value: object) -> str:
        normalized = _remarks(value)
        if normalized is None:
            raise PydanticCustomError(
                "inventory_reason_required", "Reason is required for a stock adjustment."
            )
        return normalized


class WarehouseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    is_default: bool
    archived: bool
    created_at: datetime


class StockMovementResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_code: str
    product_name: str
    warehouse_id: UUID
    warehouse_name: str
    movement_type: MovementType
    quantity: Decimal
    unit: str
    reference_type: str | None
    reference_id: UUID | None
    remarks: str | None
    created_at: datetime
    created_by: UUID
    created_by_email: str


class StockItemResponse(BaseModel):
    product_id: UUID
    product_code: str
    product_name: str
    warehouse_id: UUID
    warehouse_name: str
    available_quantity: Decimal
    unit: str
    low_stock_threshold: Decimal
    low_stock_status: LowStockStatus
    updated_at: datetime | None


class StockListResponse(BaseModel):
    items: list[StockItemResponse]
    next_cursor: str | None
    has_more: bool
    page_size: int


class MovementHistoryResponse(BaseModel):
    items: list[StockMovementResponse]
    next_cursor: str | None
    has_more: bool
    page_size: int


class InventoryMutationResponse(BaseModel):
    movement: StockMovementResponse
    stock: StockItemResponse
    message: str
