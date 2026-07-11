from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ReportPeriod = Literal["today", "yesterday", "this_week", "this_month", "custom", "all"]
SalesReportSort = Literal[
    "newest",
    "oldest",
    "amount_desc",
    "amount_asc",
    "customer_asc",
    "customer_desc",
]
PaymentReportSort = Literal[
    "newest",
    "oldest",
    "amount_desc",
    "amount_asc",
    "customer_asc",
    "customer_desc",
]
OutstandingReportSort = Literal["highest_outstanding", "alphabetical"]
InventoryReportSort = Literal[
    "name_asc",
    "name_desc",
    "stock_asc",
    "stock_desc",
    "value_asc",
    "value_desc",
]
LowStockReportSort = Literal["lowest_stock", "alphabetical"]

ReportStatusFilter = Literal["all", "draft", "posted", "void", "issued"]
SearchResultType = Literal[
    "customer",
    "product",
    "sale",
    "invoice",
    "payment",
    "inventory",
]


class DashboardMetricResponse(BaseModel):
    label: str
    value: Decimal
    unit: Literal["money", "count"]


class RecentActivityItemResponse(BaseModel):
    id: UUID
    number: str
    customer: str | None = None
    amount: Decimal | None = None
    status: str
    occurred_at: datetime
    detail_path: str


class RecentInventoryActivityResponse(BaseModel):
    id: UUID
    number: str
    product: str
    quantity: Decimal
    unit: str
    status: str
    occurred_at: datetime
    detail_path: str


class TopSellingProductResponse(BaseModel):
    product_id: UUID
    product_code: str
    product_name: str
    quantity_sold: Decimal
    total_sales: Decimal


class OutstandingCustomerResponse(BaseModel):
    customer_id: UUID
    customer_code: str
    customer_name: str
    outstanding_balance: Decimal


class DashboardResponse(BaseModel):
    business_date: date
    timezone: str
    currency: str
    today_sales: DashboardMetricResponse
    today_collections: DashboardMetricResponse
    outstanding_receivables: DashboardMetricResponse
    customer_credit: DashboardMetricResponse
    total_customers: DashboardMetricResponse
    active_products: DashboardMetricResponse
    inventory_value: DashboardMetricResponse
    low_stock_products: DashboardMetricResponse
    out_of_stock_products: DashboardMetricResponse
    recent_sales: list[RecentActivityItemResponse]
    recent_payments: list[RecentActivityItemResponse]
    recent_invoices: list[RecentActivityItemResponse]
    recent_inventory_activity: list[RecentInventoryActivityResponse]
    top_selling_products: list[TopSellingProductResponse]
    highest_outstanding_customers: list[OutstandingCustomerResponse]


class GlobalSearchItemResponse(BaseModel):
    id: UUID
    type: SearchResultType
    title: str
    subtitle: str | None = None
    reference: str
    detail_path: str


class GlobalSearchResponse(BaseModel):
    query: str
    customers: list[GlobalSearchItemResponse]
    products: list[GlobalSearchItemResponse]
    sales: list[GlobalSearchItemResponse]
    invoices: list[GlobalSearchItemResponse]
    payments: list[GlobalSearchItemResponse]
    inventory: list[GlobalSearchItemResponse]


class SalesReportRowResponse(BaseModel):
    id: UUID
    sale_number: str
    customer: str
    sale_date: date
    items: int
    subtotal: Decimal
    total: Decimal
    status: str


class SalesReportResponse(BaseModel):
    currency: str
    items: list[SalesReportRowResponse]
    next_cursor: str | None


class PaymentReportRowResponse(BaseModel):
    id: UUID
    payment_number: str
    customer: str
    payment_date: date
    amount: Decimal
    allocated: Decimal
    unallocated: Decimal
    status: str


class PaymentReportResponse(BaseModel):
    currency: str
    items: list[PaymentReportRowResponse]
    next_cursor: str | None


class OutstandingReportRowResponse(BaseModel):
    customer_id: UUID
    customer_code: str
    customer: str
    outstanding_balance: Decimal
    available_credit: Decimal
    last_sale_at: datetime | None
    last_payment_at: datetime | None


class OutstandingReportResponse(BaseModel):
    currency: str
    items: list[OutstandingReportRowResponse]
    next_cursor: str | None


class InventoryReportRowResponse(BaseModel):
    product_id: UUID
    product_code: str
    product: str
    current_stock: Decimal
    unit: str
    selling_price: Decimal
    inventory_value: Decimal
    low_stock_status: Literal["ok", "low", "out"]


class InventoryReportResponse(BaseModel):
    currency: str
    items: list[InventoryReportRowResponse]
    next_cursor: str | None


class LowStockReportResponse(BaseModel):
    currency: str
    items: list[InventoryReportRowResponse]
    next_cursor: str | None


class CsvExport(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    filename: str
    content: str
