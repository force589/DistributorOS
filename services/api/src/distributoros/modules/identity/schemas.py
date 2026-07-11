from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from pydantic_core import PydanticCustomError


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str
    email: EmailStr
    password: str

    @field_validator("business_name")
    @classmethod
    def validate_business_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise PydanticCustomError("business_name_required", "Business name is required.")
        if len(normalized) > 120:
            raise PydanticCustomError(
                "business_name_too_long",
                "Business name must not exceed 120 characters.",
            )
        return normalized

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_required(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise PydanticCustomError("email_required", "Email is required.")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value:
            raise PydanticCustomError("password_required", "Password is required.")
        if len(value) < 8:
            raise PydanticCustomError(
                "password_too_short", "Password must contain at least 8 characters."
            )
        if len(value) > 128:
            raise PydanticCustomError(
                "password_too_long", "Password must not exceed 128 characters."
            )
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_required(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise PydanticCustomError("email_required", "Email is required.")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value:
            raise PydanticCustomError("password_required", "Password is required.")
        if len(value) < 8:
            raise PydanticCustomError(
                "password_too_short", "Password must contain at least 8 characters."
            )
        if len(value) > 128:
            raise PydanticCustomError(
                "password_too_long", "Password must not exceed 128 characters."
            )
        return value


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_required(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise PydanticCustomError("email_required", "Email is required.")
        return value


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    new_password: str

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        if not value.strip():
            raise PydanticCustomError(
                "password_reset_token_required", "Open the complete password reset link."
            )
        return value.strip()

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return SignupRequest.validate_password(value)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str

    @field_validator("current_password")
    @classmethod
    def validate_current_password(cls, value: str) -> str:
        if not value:
            raise PydanticCustomError("current_password_required", "Current password is required.")
        if len(value) > 128:
            raise PydanticCustomError(
                "password_too_long", "Password must not exceed 128 characters."
            )
        return value

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return SignupRequest.validate_password(value)


class MessageResponse(BaseModel):
    message: str


class BusinessResponse(BaseModel):
    id: UUID
    business_name: str
    currency: Literal["INR", "USD", "EUR", "GBP", "AED", "SAR", "SGD", "MYR"]
    language: Literal["en", "ml"]
    theme: Literal["light", "dark", "system"]
    timezone: str


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    business: BusinessResponse


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str | None
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int
    user: UserResponse


class MeResponse(BaseModel):
    user: UserResponse


class LogoutResponse(BaseModel):
    message: str
