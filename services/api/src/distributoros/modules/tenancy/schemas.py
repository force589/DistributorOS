from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic_core import PydanticCustomError

CurrencyCode = Literal["INR", "USD", "EUR", "GBP", "AED", "SAR", "SGD", "MYR"]
LanguageCode = Literal["en", "ml"]
ThemePreference = Literal["light", "dark", "system"]


class BusinessSettingsResponse(BaseModel):
    business_name: str
    currency: CurrencyCode
    language: LanguageCode
    theme: ThemePreference
    timezone: str


class BusinessSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str | None = None
    currency: CurrencyCode | None = None
    language: LanguageCode | None = None
    theme: ThemePreference | None = None
    timezone: str | None = None

    @field_validator("business_name")
    @classmethod
    def validate_business_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise PydanticCustomError("business_name_required", "Business name is required.")
        if len(normalized) > 120:
            raise PydanticCustomError(
                "business_name_too_long",
                "Business name must not exceed 120 characters.",
            )
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise PydanticCustomError("timezone_required", "Business timezone is required.")
        if len(normalized) > 64:
            raise PydanticCustomError(
                "timezone_too_long", "Business timezone must not exceed 64 characters."
            )
        try:
            ZoneInfo(normalized)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise PydanticCustomError(
                "timezone_invalid",
                "Enter a valid IANA timezone, such as Asia/Kolkata.",
            ) from exc
        return normalized

    @model_validator(mode="after")
    def require_change(self) -> "BusinessSettingsUpdateRequest":
        if all(
            value is None
            for value in (
                self.business_name,
                self.currency,
                self.language,
                self.theme,
                self.timezone,
            )
        ):
            raise PydanticCustomError(
                "business_settings_required",
                "Change at least one business setting before saving.",
            )
        return self
