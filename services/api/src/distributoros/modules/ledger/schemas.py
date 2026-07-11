from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

LedgerEntryType = Literal["SALE", "REVERSAL", "PAYMENT", "PAYMENT_REVERSAL"]
LedgerEntryTypeFilter = Literal["all", "sale", "reversal", "payment", "payment_reversal"]


class LedgerEntryResponse(BaseModel):
    id: UUID
    entry_type: LedgerEntryType
    reference_type: Literal["SALE", "PAYMENT"]
    reference_id: UUID
    reference: str
    debit: Decimal
    credit: Decimal
    running_balance: Decimal
    remarks: str | None
    created_at: datetime


class LedgerListResponse(BaseModel):
    items: list[LedgerEntryResponse]
    next_cursor: str | None
    has_more: bool
    page_size: int


class CustomerFinancialSummaryResponse(BaseModel):
    customer_id: UUID
    outstanding_balance: Decimal
    available_credit: Decimal
    total_sales: Decimal
    total_payments: Decimal
    last_sale_date: datetime | None
    last_payment_date: datetime | None
