from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

InvoiceStatus = Literal["DRAFT", "ISSUED", "VOID"]
InvoiceStatusFilter = Literal["all", "draft", "issued", "void"]
InvoiceSort = Literal["newest", "oldest"]


class InvoiceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_id: UUID


class InvoiceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    line_number: int
    product_snapshot: str
    unit_snapshot: str
    unit_price_snapshot: Decimal
    quantity_snapshot: Decimal
    line_total: Decimal
    created_at: datetime


class InvoiceResponse(BaseModel):
    id: UUID
    invoice_number: str
    sale_id: UUID
    sale_number: str
    customer_id: UUID
    status: InvoiceStatus
    issue_date: date
    currency: str
    subtotal: Decimal
    tax_total: Decimal
    grand_total: Decimal
    allocated_amount: Decimal
    outstanding_amount: Decimal
    pdf_path: str
    customer_name_snapshot: str
    customer_phone_snapshot: str | None
    customer_address_line_1_snapshot: str | None
    customer_address_line_2_snapshot: str | None
    customer_city_snapshot: str | None
    customer_state_snapshot: str | None
    customer_postal_code_snapshot: str | None
    created_at: datetime
    created_by: UUID
    items: list[InvoiceItemResponse]


class InvoiceListItemResponse(BaseModel):
    id: UUID
    invoice_number: str
    sale_id: UUID
    sale_number: str
    customer_id: UUID
    customer_name: str
    status: InvoiceStatus
    issue_date: date
    currency: str
    grand_total: Decimal
    allocated_amount: Decimal
    outstanding_amount: Decimal
    created_at: datetime


class InvoiceListResponse(BaseModel):
    items: list[InvoiceListItemResponse]
    next_cursor: str | None
    has_more: bool
    page_size: int


class InvoiceMutationResponse(BaseModel):
    invoice: InvoiceResponse
    message: str
