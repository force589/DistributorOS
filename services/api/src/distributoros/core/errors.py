from dataclasses import dataclass
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


@dataclass
class AppError(Exception):
    status_code: int
    code: str
    message: str
    field_errors: dict[str, str] | None = None
    headers: dict[str, str] | None = None


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    field_errors: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", None),
        }
    }
    if field_errors:
        content["error"]["field_errors"] = field_errors
    response_headers = dict(headers or {})
    if status_code == 401:
        response_headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(status_code=status_code, content=content, headers=response_headers or None)


def _friendly_validation_message(error: dict[str, Any]) -> tuple[str, str]:
    location = error.get("loc", ())
    field = str(location[-1]) if location else "request"
    error_type = str(error.get("type", ""))

    custom_error_types = {
        "business_name_required",
        "business_name_too_long",
        "business_settings_required",
        "email_required",
        "password_required",
        "password_too_short",
        "password_too_long",
        "customer_name_required",
        "customer_name_too_long",
        "customer_email_invalid",
        "customer_phone_invalid",
        "customer_text_invalid",
        "customer_field_too_long",
        "product_name_required",
        "product_name_too_long",
        "product_text_invalid",
        "product_field_too_long",
        "selling_price_required",
        "selling_price_invalid",
        "selling_price_negative",
        "selling_price_too_large",
        "selling_price_precision",
        "low_stock_threshold_required",
        "low_stock_threshold_invalid",
        "low_stock_threshold_negative",
        "low_stock_threshold_too_large",
        "low_stock_threshold_precision",
        "product_unit_required",
        "product_unit_invalid",
        "inventory_quantity_required",
        "inventory_quantity_invalid",
        "inventory_quantity_zero",
        "inventory_quantity_positive",
        "inventory_quantity_too_large",
        "inventory_quantity_precision",
        "inventory_remarks_invalid",
        "inventory_remarks_too_long",
        "inventory_reason_required",
        "sale_quantity_required",
        "sale_quantity_invalid",
        "sale_quantity_positive",
        "sale_quantity_too_large",
        "sale_quantity_precision",
        "sale_unit_price_required",
        "sale_unit_price_invalid",
        "sale_unit_price_positive",
        "sale_unit_price_too_large",
        "sale_unit_price_precision",
        "payment_amount_required",
        "payment_amount_invalid",
        "payment_amount_positive",
        "payment_amount_too_large",
        "payment_amount_precision",
        "payment_allocation_amount_required",
        "payment_allocation_amount_invalid",
        "payment_allocation_amount_positive",
        "payment_allocation_amount_too_large",
        "payment_allocation_amount_precision",
        "payment_allocation_target_required",
        "payment_text_too_long",
    }
    if error_type in custom_error_types:
        return field, str(error.get("msg", "Please check this value and try again."))
    if error_type == "extra_forbidden":
        readable_field = field.replace("_", " ")
        return field, f"{readable_field.capitalize()} is not accepted. Remove it and try again."

    if error_type == "missing":
        messages = {
            "business_name": "Business name is required.",
            "email": "Email is required.",
            "password": "Password is required.",
            "name": "Customer name is required.",
            "q": "Enter a customer name, phone number, email, or customer code.",
            "selling_price": "Selling price is required.",
            "unit": "Unit is required.",
            "low_stock_threshold": "Low stock threshold is required.",
            "product_id": "Select a product.",
            "quantity": "Quantity is required.",
            "reason": "Reason is required for a stock adjustment.",
            "customer_id": "Select a customer.",
            "items": "Add at least one product.",
        }
        return field, messages.get(field, "This field is required.")
    if field == "email":
        return field, "Please enter a valid email."
    if field == "password" and error_type == "string_too_short":
        return field, "Password must contain at least 8 characters."
    if field == "business_name":
        return field, "Business name is required."
    if field == "limit":
        return field, "Page size must be between 1 and 100 customers."
    if field in {"status", "sort"}:
        return field, f"Choose a supported customer {field} option."

    message = str(error.get("msg", "Please check this value and try again."))
    return field, message.removeprefix("Value error, ")


def _friendly_sales_validation_message(error: dict[str, Any]) -> tuple[str, str]:
    location = tuple(error.get("loc", ()))
    error_type = str(error.get("type", ""))
    field = str(location[-1]) if location else "request"
    if "items" in location:
        items_index = location.index("items")
        nested = location[items_index:]
        field = ".".join(str(part) for part in nested)
    custom_field, custom_message = _friendly_validation_message(error)
    if error_type.startswith("sale_"):
        return field, custom_message
    if field.endswith(".product_id"):
        return field, "Select a valid product."
    if field.endswith(".unit_price") and error_type == "missing":
        return field, "Unit price is required."
    if field == "items":
        if error_type in {"too_short", "list_too_short"}:
            return field, "Add at least one product to this sale."
        if error_type in {"too_long", "list_too_long"}:
            return field, "A sale can contain at most 100 products."
    messages = {
        "customer_id": "Select a valid customer.",
        "product_id": "Select a valid product.",
        "sale_id": "Open the sale from the sales list and try again.",
        "date": "Enter the sale date as YYYY-MM-DD.",
        "status": "Choose All Sales, Draft, Posted, or Void.",
        "sort": "Choose Newest or Oldest.",
        "limit": "Page size must be between 1 and 100 sales.",
        "cursor": "Refresh the sales list before loading more.",
        "q": "Enter a sale number or customer name with no more than 160 characters.",
        "search": "Search must not exceed 160 characters.",
    }
    if field in messages:
        return field, messages[field]
    return field if field != custom_field else custom_field, custom_message


def _friendly_ledger_validation_message(error: dict[str, Any]) -> tuple[str, str]:
    location = tuple(error.get("loc", ()))
    field = str(location[-1]) if location else "request"
    messages = {
        "customer_id": "Open the customer from the customer list and try again.",
        "date": "Enter the ledger date as YYYY-MM-DD.",
        "entry_type": ("Choose All Entries, Sales, Reversals, Payments, or Payment Reversals."),
        "limit": "Page size must be between 1 and 100 ledger entries.",
        "cursor": "Refresh the customer ledger before loading more.",
        "q": "Enter a sale or payment reference with no more than 160 characters.",
        "reference": "Sale or payment reference must not exceed 160 characters.",
    }
    if field in messages:
        return field, messages[field]
    return _friendly_validation_message(error)


def _friendly_payment_validation_message(error: dict[str, Any]) -> tuple[str, str]:
    location = tuple(error.get("loc", ()))
    error_type = str(error.get("type", ""))
    field = str(location[-1]) if location else "request"
    if "allocations" in location:
        allocation_index = location.index("allocations")
        field = ".".join(str(part) for part in location[allocation_index:])
    custom_field, custom_message = _friendly_validation_message(error)
    if error_type.startswith("payment_"):
        return field, custom_message
    messages = {
        "payment_id": "Open the payment from the payments list and try again.",
        "customer_id": "Select a valid customer.",
        "amount": "Payment amount is required.",
        "payment_date": "Enter the payment date as YYYY-MM-DD.",
        "payment_method": "Choose Cash, UPI, Bank Transfer, Cheque, or Other.",
        "allocations": "Check payment allocations and try again.",
        "method": "Choose All Methods, Cash, UPI, Bank Transfer, Cheque, or Other.",
        "status": "Choose All Payments, Posted, or Void.",
        "sort": "Choose Newest or Oldest.",
        "limit": "Page size must be between 1 and 100 payments.",
        "cursor": "Refresh the payments list before loading more.",
        "q": "Enter a payment number, reference, customer, or method.",
        "search": "Search must not exceed 160 characters.",
        "date": "Enter the payment date as YYYY-MM-DD.",
    }
    if field.endswith(".ledger_entry_id"):
        return field, "Select a valid ledger entry."
    if field.endswith(".invoice_id"):
        return field, "Select a valid issued invoice."
    if field.endswith(".allocated_amount") and error_type == "missing":
        return field, "Allocation amount is required."
    if field in messages:
        return field, messages[field]
    return field if field != custom_field else custom_field, custom_message


def _friendly_invoice_validation_message(error: dict[str, Any]) -> tuple[str, str]:
    location = tuple(error.get("loc", ()))
    field = str(location[-1]) if location else "request"
    messages = {
        "invoice_id": "Open the invoice from the invoice list and try again.",
        "invoice_number": "Open the invoice from the invoice list and try again.",
        "customer_id": "Open the customer from the customer list and try again.",
        "sale_id": "Select a posted sale that does not already have an invoice.",
        "date": "Enter the invoice date as YYYY-MM-DD.",
        "status": "Choose All Invoices, Draft, Issued, or Void.",
        "sort": "Choose Newest or Oldest.",
        "limit": "Page size must be between 1 and 100 invoices.",
        "cursor": "Refresh the invoice list before loading more.",
        "q": "Enter an invoice number, sale number, or customer name.",
        "search": "Search must not exceed 160 characters.",
    }
    if field in messages:
        return field, messages[field]
    return _friendly_validation_message(error)


def install_exception_handlers(app: FastAPI) -> None:
    logger = structlog.get_logger("distributoros.errors")

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            field_errors=exc.field_errors,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors: dict[str, str] = {}
        for error in exc.errors():
            if str(error.get("type", "")) == "json_invalid":
                field_errors.setdefault(
                    "request",
                    "The request body is not valid JSON. Check its syntax and try again.",
                )
                continue
            if "/ledger" in request.url.path or request.url.path.endswith("/financial-summary"):
                field, message = _friendly_ledger_validation_message(error)
            elif request.url.path.startswith("/api/v1/invoices") or (
                request.url.path.startswith("/api/v1/customers")
                and request.url.path.endswith("/invoices")
            ):
                field, message = _friendly_invoice_validation_message(error)
            elif request.url.path.startswith("/api/v1/payments") or (
                request.url.path.startswith("/api/v1/customers")
                and (
                    request.url.path.endswith("/payments")
                    or request.url.path.endswith("/credit")
                    or request.url.path.endswith("/balance")
                )
            ):
                field, message = _friendly_payment_validation_message(error)
            elif request.url.path.startswith("/api/v1/sales"):
                field, message = _friendly_sales_validation_message(error)
            else:
                field, message = _friendly_validation_message(error)
            if (
                field == "name"
                and str(error.get("type", "")) == "missing"
                and request.url.path.startswith("/api/v1/products")
            ):
                message = "Product name is required."
            field_errors.setdefault(field, message)
        first_message = next(
            iter(field_errors.values()),
            "The request could not be read. Check the submitted information and try again.",
        )
        return error_response(
            request,
            status_code=422,
            code="VALIDATION_ERROR",
            message=first_message,
            field_errors=field_errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        messages = {
            403: (
                "FORBIDDEN",
                "You do not have permission to perform this action. "
                "Contact a business owner if you need access.",
            ),
            404: (
                "NOT_FOUND",
                "The requested resource was not found. Check the address and try again.",
            ),
            405: (
                "ACTION_NOT_SUPPORTED",
                "This action is not supported for this resource. "
                "Refresh the page and use an available action.",
            ),
        }
        code, message = messages.get(
            exc.status_code,
            ("HTTP_ERROR", "The request could not be completed. Check it and try again."),
        )
        return error_response(
            request,
            status_code=exc.status_code,
            code=code,
            message=message,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            request_id=getattr(request.state, "request_id", None),
            path=request.url.path,
            method=request.method,
            exception_type=type(exc).__name__,
        )
        return error_response(
            request,
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message=(
                "We could not complete your request because of an unexpected server error. "
                "Please try again."
            ),
        )
