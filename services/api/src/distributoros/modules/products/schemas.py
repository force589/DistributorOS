from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic_core import PydanticCustomError

ProductStatus = Literal["all", "active", "archived"]
ProductSort = Literal["newest", "oldest", "name_asc", "name_desc", "price_asc", "price_desc"]
ProductUnit = Literal["piece", "kg", "gram", "litre", "millilitre", "box", "packet", "dozen"]

NAME_MAX_LENGTH = 160
DESCRIPTION_MAX_LENGTH = 2000
SELLING_PRICE_MAX = Decimal("999999999999.99")
THRESHOLD_MAX = Decimal("999999999999999.999")
SUPPORTED_UNITS = {
    "piece",
    "kg",
    "gram",
    "litre",
    "millilitre",
    "box",
    "packet",
    "dozen",
}


def _required_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PydanticCustomError("product_name_required", "Product name is required.")
    normalized = value.strip()
    if len(normalized) > NAME_MAX_LENGTH:
        raise PydanticCustomError(
            "product_name_too_long",
            f"Product name must not exceed {NAME_MAX_LENGTH} characters.",
        )
    return normalized


def _optional_text(value: object, *, label: str, max_length: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PydanticCustomError("product_text_invalid", f"{label} must be text.")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise PydanticCustomError(
            "product_field_too_long",
            f"{label} must not exceed {max_length} characters.",
        )
    return normalized


def _required_decimal(
    value: object,
    *,
    field_name: str,
    label: str,
    max_value: Decimal,
    decimal_places: int,
) -> Decimal:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise PydanticCustomError(f"{field_name}_required", f"{label} is required.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PydanticCustomError(
            f"{field_name}_invalid", f"Enter a valid {label.lower()}."
        ) from exc
    if not number.is_finite():
        raise PydanticCustomError(f"{field_name}_invalid", f"Enter a valid {label.lower()}.")
    if number < 0:
        raise PydanticCustomError(f"{field_name}_negative", f"{label} cannot be negative.")
    if number > max_value:
        raise PydanticCustomError(
            f"{field_name}_too_large", f"{label} is too large. Enter a smaller value."
        )
    exponent = number.as_tuple().exponent
    if isinstance(exponent, int) and max(-exponent, 0) > decimal_places:
        raise PydanticCustomError(
            f"{field_name}_precision",
            f"{label} can have at most {decimal_places} decimal places.",
        )
    quantum = Decimal(1).scaleb(-decimal_places)
    return number.quantize(quantum)


def _required_unit(value: object) -> ProductUnit:
    if not isinstance(value, str) or not value.strip():
        raise PydanticCustomError("product_unit_required", "Unit is required.")
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_UNITS:
        raise PydanticCustomError("product_unit_invalid", "Choose a supported product unit.")
    return normalized  # type: ignore[return-value]


class ProductFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    sku: str | None = None
    barcode: str | None = None
    category: str | None = None
    description: str | None = None
    selling_price: Decimal
    unit: ProductUnit
    low_stock_threshold: Decimal

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return _required_name(value)

    @field_validator("sku", mode="before")
    @classmethod
    def validate_sku(cls, value: object) -> str | None:
        return _optional_text(value, label="SKU", max_length=100)

    @field_validator("barcode", mode="before")
    @classmethod
    def validate_barcode(cls, value: object) -> str | None:
        return _optional_text(value, label="Barcode", max_length=128)

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, value: object) -> str | None:
        return _optional_text(value, label="Category", max_length=100)

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value: object) -> str | None:
        return _optional_text(value, label="Description", max_length=DESCRIPTION_MAX_LENGTH)

    @field_validator("selling_price", mode="before")
    @classmethod
    def validate_selling_price(cls, value: object) -> Decimal:
        return _required_decimal(
            value,
            field_name="selling_price",
            label="Selling price",
            max_value=SELLING_PRICE_MAX,
            decimal_places=2,
        )

    @field_validator("unit", mode="before")
    @classmethod
    def validate_unit(cls, value: object) -> ProductUnit:
        return _required_unit(value)

    @field_validator("low_stock_threshold", mode="before")
    @classmethod
    def validate_threshold(cls, value: object) -> Decimal:
        return _required_decimal(
            value,
            field_name="low_stock_threshold",
            label="Low stock threshold",
            max_value=THRESHOLD_MAX,
            decimal_places=3,
        )


class ProductCreateRequest(ProductFields):
    pass


class ProductUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    sku: str | None = None
    barcode: str | None = None
    category: str | None = None
    description: str | None = None
    selling_price: Decimal | None = None
    unit: ProductUnit | None = None
    low_stock_threshold: Decimal | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return _required_name(value)

    @field_validator("sku", mode="before")
    @classmethod
    def validate_sku(cls, value: object) -> str | None:
        return _optional_text(value, label="SKU", max_length=100)

    @field_validator("barcode", mode="before")
    @classmethod
    def validate_barcode(cls, value: object) -> str | None:
        return _optional_text(value, label="Barcode", max_length=128)

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, value: object) -> str | None:
        return _optional_text(value, label="Category", max_length=100)

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value: object) -> str | None:
        return _optional_text(value, label="Description", max_length=DESCRIPTION_MAX_LENGTH)

    @field_validator("selling_price", mode="before")
    @classmethod
    def validate_selling_price(cls, value: object) -> Decimal:
        return _required_decimal(
            value,
            field_name="selling_price",
            label="Selling price",
            max_value=SELLING_PRICE_MAX,
            decimal_places=2,
        )

    @field_validator("unit", mode="before")
    @classmethod
    def validate_unit(cls, value: object) -> ProductUnit:
        return _required_unit(value)

    @field_validator("low_stock_threshold", mode="before")
    @classmethod
    def validate_threshold(cls, value: object) -> Decimal:
        return _required_decimal(
            value,
            field_name="low_stock_threshold",
            label="Low stock threshold",
            max_value=THRESHOLD_MAX,
            decimal_places=3,
        )


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_code: str
    name: str
    sku: str | None
    barcode: str | None
    category: str | None
    description: str | None
    selling_price: Decimal
    unit: ProductUnit
    low_stock_threshold: Decimal
    archived: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    next_cursor: str | None
    has_more: bool
    page_size: int


class ProductMutationResponse(BaseModel):
    product: ProductResponse
    message: str
