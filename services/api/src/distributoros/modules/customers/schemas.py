import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, TypeAdapter, ValidationError, field_validator
from pydantic_core import PydanticCustomError

CustomerStatus = Literal["all", "active", "archived"]
CustomerSort = Literal["newest", "oldest", "name_asc", "name_desc"]

NAME_MAX_LENGTH = 160
NOTES_MAX_LENGTH = 2000
EMAIL_ADAPTER = TypeAdapter(EmailStr)


def _required_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PydanticCustomError("customer_name_required", "Customer name is required.")
    normalized = value.strip()
    if len(normalized) > NAME_MAX_LENGTH:
        raise PydanticCustomError(
            "customer_name_too_long",
            f"Customer name must not exceed {NAME_MAX_LENGTH} characters.",
        )
    return normalized


def _optional_text(value: object, *, label: str, max_length: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PydanticCustomError("customer_text_invalid", f"{label} must be text.")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise PydanticCustomError(
            "customer_field_too_long",
            f"{label} must not exceed {max_length} characters.",
        )
    return normalized


def _optional_email(value: object) -> str | None:
    normalized = _optional_text(value, label="Email", max_length=320)
    if normalized is None:
        return None
    try:
        return str(EMAIL_ADAPTER.validate_python(normalized))
    except ValidationError as exc:
        raise PydanticCustomError(
            "customer_email_invalid", "Please enter a valid email address."
        ) from exc


def _optional_phone(value: object) -> str | None:
    normalized = _optional_text(value, label="Phone number", max_length=32)
    if normalized is None:
        return None
    digits = re.sub(r"\D", "", normalized)
    if len(digits) < 7 or len(digits) > 15 or not re.fullmatch(r"\+?[0-9][0-9 ()-]*", normalized):
        raise PydanticCustomError("customer_phone_invalid", "Please enter a valid phone number.")
    return normalized


class CustomerFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    phone: str | None = None
    email: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    notes: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return _required_name(value)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, value: object) -> str | None:
        return _optional_phone(value)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str | None:
        return _optional_email(value)

    @field_validator("address_line_1", mode="before")
    @classmethod
    def validate_address_line_1(cls, value: object) -> str | None:
        return _optional_text(value, label="Address line 1", max_length=200)

    @field_validator("address_line_2", mode="before")
    @classmethod
    def validate_address_line_2(cls, value: object) -> str | None:
        return _optional_text(value, label="Address line 2", max_length=200)

    @field_validator("city", mode="before")
    @classmethod
    def validate_city(cls, value: object) -> str | None:
        return _optional_text(value, label="City", max_length=100)

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, value: object) -> str | None:
        return _optional_text(value, label="State", max_length=100)

    @field_validator("postal_code", mode="before")
    @classmethod
    def validate_postal_code(cls, value: object) -> str | None:
        return _optional_text(value, label="Postal code", max_length=20)

    @field_validator("notes", mode="before")
    @classmethod
    def validate_notes(cls, value: object) -> str | None:
        return _optional_text(value, label="Notes", max_length=NOTES_MAX_LENGTH)


class CustomerCreateRequest(CustomerFields):
    pass


class CustomerUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    notes: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return _required_name(value)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, value: object) -> str | None:
        return _optional_phone(value)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str | None:
        return _optional_email(value)

    @field_validator("address_line_1", "address_line_2", mode="before")
    @classmethod
    def validate_address(cls, value: object) -> str | None:
        return _optional_text(value, label="Address line", max_length=200)

    @field_validator("city", mode="before")
    @classmethod
    def validate_city(cls, value: object) -> str | None:
        return _optional_text(value, label="City", max_length=100)

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, value: object) -> str | None:
        return _optional_text(value, label="State", max_length=100)

    @field_validator("postal_code", mode="before")
    @classmethod
    def validate_postal_code(cls, value: object) -> str | None:
        return _optional_text(value, label="Postal code", max_length=20)

    @field_validator("notes", mode="before")
    @classmethod
    def validate_notes(cls, value: object) -> str | None:
        return _optional_text(value, label="Notes", max_length=NOTES_MAX_LENGTH)


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_code: str
    name: str
    phone: str | None
    email: str | None
    address_line_1: str | None
    address_line_2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    notes: str | None
    archived: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    next_cursor: str | None
    has_more: bool
    page_size: int


class CustomerMutationResponse(BaseModel):
    customer: CustomerResponse
    message: str
