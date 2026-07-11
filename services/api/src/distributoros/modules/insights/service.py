from __future__ import annotations

import base64
import csv
import io
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.errors import AppError
from distributoros.modules.insights.schemas import (
    CsvExport,
    DashboardMetricResponse,
    DashboardResponse,
    GlobalSearchItemResponse,
    GlobalSearchResponse,
    InventoryReportResponse,
    InventoryReportRowResponse,
    InventoryReportSort,
    LowStockReportResponse,
    LowStockReportSort,
    OutstandingCustomerResponse,
    OutstandingReportResponse,
    OutstandingReportRowResponse,
    OutstandingReportSort,
    PaymentReportResponse,
    PaymentReportRowResponse,
    PaymentReportSort,
    RecentActivityItemResponse,
    RecentInventoryActivityResponse,
    ReportPeriod,
    ReportStatusFilter,
    SalesReportResponse,
    SalesReportRowResponse,
    SalesReportSort,
    TopSellingProductResponse,
)

DEFAULT_BUSINESS_TIMEZONE = "Asia/Kolkata"
DEFAULT_LIMIT = 25
MAX_LIMIT = 100
CSV_EXPORT_LIMIT = 50_000


@dataclass(frozen=True)
class DateRange:
    date_from: date | None
    date_to: date | None


@dataclass(frozen=True)
class DashboardCollections:
    recent_sales: list[RecentActivityItemResponse]
    recent_payments: list[RecentActivityItemResponse]
    recent_invoices: list[RecentActivityItemResponse]
    recent_inventory: list[RecentInventoryActivityResponse]
    top_selling_products: list[TopSellingProductResponse]
    highest_outstanding_customers: list[OutstandingCustomerResponse]


class InsightsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def dashboard(self, tenant_id: UUID) -> DashboardResponse:
        timezone = await self._business_timezone(tenant_id)
        business_date = self._today(timezone)
        collections = await self._dashboard_collections(tenant_id)
        metrics = (
            (
                await self.session.execute(
                    text(
                        """
                    WITH product_stock AS (
                        SELECT
                            product.id,
                            product.low_stock_threshold,
                            product.selling_price,
                            COALESCE(SUM(balance.available_quantity), 0) AS current_stock
                        FROM products product
                        LEFT JOIN stock_balances balance
                          ON balance.tenant_id = product.tenant_id
                         AND balance.product_id = product.id
                        WHERE product.tenant_id = :tenant_id
                          AND product.archived = false
                        GROUP BY
                            product.id,
                            product.low_stock_threshold,
                            product.selling_price
                    )
                    SELECT
                      (
                        SELECT COALESCE(SUM(sale.subtotal), 0)
                        FROM sales sale
                        WHERE sale.tenant_id = :tenant_id
                          AND sale.status = 'POSTED'
                          AND DATE(sale.created_at AT TIME ZONE :timezone) = :business_date
                      ) AS today_sales,
                      (
                        SELECT COALESCE(SUM(payment.amount), 0)
                        FROM payments payment
                        WHERE payment.tenant_id = :tenant_id
                          AND payment.status = 'POSTED'
                          AND payment.payment_date = :business_date
                      ) AS today_collections,
                      (
                        SELECT COALESCE(SUM(balance.outstanding_balance), 0)
                        FROM customer_balance_projections balance
                        WHERE balance.tenant_id = :tenant_id
                      ) AS outstanding_receivables,
                      (
                        SELECT COALESCE(SUM(balance.available_credit), 0)
                        FROM customer_balance_projections balance
                        WHERE balance.tenant_id = :tenant_id
                      ) AS customer_credit,
                      (
                        SELECT COUNT(*)
                        FROM customers customer
                        WHERE customer.tenant_id = :tenant_id
                          AND customer.archived = false
                      ) AS total_customers,
                      (
                        SELECT COUNT(*)
                        FROM products product
                        WHERE product.tenant_id = :tenant_id
                          AND product.archived = false
                      ) AS active_products,
                      (
                        SELECT COALESCE(SUM(current_stock * selling_price), 0)
                        FROM product_stock
                      ) AS inventory_value,
                      (
                        SELECT COUNT(*)
                        FROM product_stock
                        WHERE current_stock > 0
                          AND current_stock <= low_stock_threshold
                      ) AS low_stock_products,
                      (
                        SELECT COUNT(*)
                        FROM product_stock
                        WHERE current_stock <= 0
                      ) AS out_of_stock_products
                    """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "timezone": timezone,
                        "business_date": business_date,
                    },
                )
            )
            .mappings()
            .one()
        )
        return DashboardResponse(
            business_date=business_date,
            timezone=timezone,
            currency=await self._business_currency(tenant_id),
            today_sales=self._metric("Today's Sales", metrics["today_sales"], "money"),
            today_collections=self._metric(
                "Today's Collections", metrics["today_collections"], "money"
            ),
            outstanding_receivables=self._metric(
                "Outstanding Receivables", metrics["outstanding_receivables"], "money"
            ),
            customer_credit=self._metric("Customer Credit", metrics["customer_credit"], "money"),
            total_customers=self._metric("Total Customers", metrics["total_customers"], "count"),
            active_products=self._metric("Active Products", metrics["active_products"], "count"),
            inventory_value=self._metric("Inventory Value", metrics["inventory_value"], "money"),
            low_stock_products=self._metric(
                "Low Stock Products", metrics["low_stock_products"], "count"
            ),
            out_of_stock_products=self._metric(
                "Out of Stock Products", metrics["out_of_stock_products"], "count"
            ),
            recent_sales=collections.recent_sales,
            recent_payments=collections.recent_payments,
            recent_invoices=collections.recent_invoices,
            recent_inventory_activity=collections.recent_inventory,
            top_selling_products=collections.top_selling_products,
            highest_outstanding_customers=collections.highest_outstanding_customers,
        )

    async def _dashboard_collections(self, tenant_id: UUID) -> DashboardCollections:
        row = (
            (
                await self.session.execute(
                    text(
                        """
                    SELECT
                      COALESCE((
                        SELECT jsonb_agg(jsonb_build_object(
                          'id', item.id, 'number', item.number, 'customer', item.customer,
                          'amount', item.amount, 'status', item.status,
                          'occurred_at', item.occurred_at,
                          'detail_path', '/sales/' || item.number
                        ) ORDER BY item.occurred_at DESC, item.id DESC)
                        FROM (
                          SELECT sale.id, sale.sale_number AS number,
                                 customer.name AS customer, sale.subtotal AS amount,
                                 sale.status, sale.created_at AS occurred_at
                          FROM sales sale
                          JOIN customers customer
                            ON customer.tenant_id = sale.tenant_id
                           AND customer.id = sale.customer_id
                          WHERE sale.tenant_id = :tenant_id
                          ORDER BY sale.created_at DESC, sale.id DESC LIMIT 5
                        ) item
                      ), '[]'::jsonb) AS recent_sales,
                      COALESCE((
                        SELECT jsonb_agg(jsonb_build_object(
                          'id', item.id, 'number', item.number, 'customer', item.customer,
                          'amount', item.amount, 'status', item.status,
                          'occurred_at', item.occurred_at,
                          'detail_path', '/payments/' || item.number
                        ) ORDER BY item.occurred_at DESC, item.id DESC)
                        FROM (
                          SELECT payment.id, payment.payment_number AS number,
                                 customer.name AS customer, payment.amount,
                                 payment.status, payment.created_at AS occurred_at
                          FROM payments payment
                          JOIN customers customer
                            ON customer.tenant_id = payment.tenant_id
                           AND customer.id = payment.customer_id
                          WHERE payment.tenant_id = :tenant_id
                          ORDER BY payment.created_at DESC, payment.id DESC LIMIT 5
                        ) item
                      ), '[]'::jsonb) AS recent_payments,
                      COALESCE((
                        SELECT jsonb_agg(jsonb_build_object(
                          'id', item.id, 'number', item.number, 'customer', item.customer,
                          'amount', item.amount, 'status', item.status,
                          'occurred_at', item.occurred_at,
                          'detail_path', '/invoices/' || item.number
                        ) ORDER BY item.occurred_at DESC, item.id DESC)
                        FROM (
                          SELECT id, invoice_number AS number,
                                 customer_name_snapshot AS customer,
                                 grand_total AS amount, status, created_at AS occurred_at
                          FROM invoices WHERE tenant_id = :tenant_id
                          ORDER BY created_at DESC, id DESC LIMIT 5
                        ) item
                      ), '[]'::jsonb) AS recent_invoices,
                      COALESCE((
                        SELECT jsonb_agg(jsonb_build_object(
                          'id', item.id, 'number', item.number, 'product', item.product,
                          'quantity', item.quantity, 'unit', item.unit,
                          'status', item.status, 'occurred_at', item.occurred_at,
                          'detail_path', '/inventory/' || item.number
                        ) ORDER BY item.occurred_at DESC, item.id DESC)
                        FROM (
                          SELECT movement.id, product.product_code AS number,
                                 product.name AS product, movement.quantity, movement.unit,
                                 movement.movement_type AS status,
                                 movement.created_at AS occurred_at
                          FROM stock_movements movement
                          JOIN products product
                            ON product.tenant_id = movement.tenant_id
                           AND product.id = movement.product_id
                          WHERE movement.tenant_id = :tenant_id
                          ORDER BY movement.created_at DESC, movement.id DESC LIMIT 5
                        ) item
                      ), '[]'::jsonb) AS recent_inventory,
                      COALESCE((
                        SELECT jsonb_agg(jsonb_build_object(
                          'product_id', item.product_id,
                          'product_code', item.product_code,
                          'product_name', item.product_name,
                          'quantity_sold', item.quantity_sold,
                          'total_sales', item.total_sales
                        ) ORDER BY item.total_sales DESC, item.quantity_sold DESC,
                                   item.product_name ASC)
                        FROM (
                          SELECT sale_item.product_id, product.product_code,
                                 sale_item.product_name_snapshot AS product_name,
                                 COALESCE(SUM(sale_item.quantity), 0) AS quantity_sold,
                                 COALESCE(SUM(sale_item.line_total), 0) AS total_sales
                          FROM sale_items sale_item
                          JOIN sales sale ON sale.id = sale_item.sale_id
                          JOIN products product
                            ON product.tenant_id = sale.tenant_id
                           AND product.id = sale_item.product_id
                          WHERE sale.tenant_id = :tenant_id AND sale.status = 'POSTED'
                          GROUP BY sale_item.product_id, product.product_code,
                                   sale_item.product_name_snapshot
                          ORDER BY total_sales DESC, quantity_sold DESC, product_name ASC
                          LIMIT 5
                        ) item
                      ), '[]'::jsonb) AS top_selling_products,
                      COALESCE((
                        SELECT jsonb_agg(jsonb_build_object(
                          'customer_id', item.customer_id,
                          'customer_code', item.customer_code,
                          'customer_name', item.customer_name,
                          'outstanding_balance', item.outstanding_balance
                        ) ORDER BY item.outstanding_balance DESC,
                                   lower(item.customer_name), item.customer_id)
                        FROM (
                          SELECT customer.id AS customer_id, customer.customer_code,
                                 customer.name AS customer_name,
                                 balance.outstanding_balance
                          FROM customer_balance_projections balance
                          JOIN customers customer
                            ON customer.tenant_id = balance.tenant_id
                           AND customer.id = balance.customer_id
                          WHERE balance.tenant_id = :tenant_id
                            AND balance.outstanding_balance > 0
                          ORDER BY balance.outstanding_balance DESC,
                                   lower(customer.name), customer.id
                          LIMIT 5
                        ) item
                      ), '[]'::jsonb) AS highest_outstanding_customers
                    """
                    ),
                    {"tenant_id": tenant_id},
                )
            )
            .mappings()
            .one()
        )
        return DashboardCollections(
            recent_sales=[
                RecentActivityItemResponse.model_validate(item) for item in row["recent_sales"]
            ],
            recent_payments=[
                RecentActivityItemResponse.model_validate(item) for item in row["recent_payments"]
            ],
            recent_invoices=[
                RecentActivityItemResponse.model_validate(item) for item in row["recent_invoices"]
            ],
            recent_inventory=[
                RecentInventoryActivityResponse.model_validate(item)
                for item in row["recent_inventory"]
            ],
            top_selling_products=[
                TopSellingProductResponse.model_validate(item)
                for item in row["top_selling_products"]
            ],
            highest_outstanding_customers=[
                OutstandingCustomerResponse.model_validate(item)
                for item in row["highest_outstanding_customers"]
            ],
        )

    async def global_search(
        self, tenant_id: UUID, query: str, *, limit_per_group: int
    ) -> GlobalSearchResponse:
        normalized = query.strip()
        if not normalized:
            raise AppError(
                status_code=422,
                code="GLOBAL_SEARCH_QUERY_REQUIRED",
                message="Enter a search term to search your business records.",
                field_errors={
                    "q": ("Enter a customer, product, sale, invoice, or payment search term.")
                },
            )
        if len(normalized) < 2:
            raise AppError(
                status_code=422,
                code="GLOBAL_SEARCH_QUERY_TOO_SHORT",
                message="Enter at least 2 characters to search your business records.",
                field_errors={"q": "Search must contain at least 2 characters."},
            )
        limit = self._limit(limit_per_group, default=5, maximum=10)
        term = self._search_term(normalized)
        params = {"tenant_id": tenant_id, "term": term, "limit": limit}
        return GlobalSearchResponse(
            query=normalized,
            customers=[
                GlobalSearchItemResponse(
                    id=row["id"],
                    type="customer",
                    title=row["name"],
                    subtitle=row["phone"] or row["email"],
                    reference=row["customer_code"],
                    detail_path=f"/customers/{row['customer_code']}",
                )
                for row in await self._rows(
                    """
                    SELECT id, customer_code, name, phone, email
                    FROM customers
                    WHERE tenant_id = :tenant_id
                      AND archived = false
                      AND (
                        lower(name) LIKE :term ESCAPE '\\'
                        OR lower(customer_code) LIKE :term ESCAPE '\\'
                        OR lower(COALESCE(phone, '')) LIKE :term ESCAPE '\\'
                        OR lower(COALESCE(email, '')) LIKE :term ESCAPE '\\'
                      )
                    ORDER BY lower(name), id
                    LIMIT :limit
                    """,
                    params,
                )
            ],
            products=[
                GlobalSearchItemResponse(
                    id=row["id"],
                    type="product",
                    title=row["name"],
                    subtitle=row["sku"] or row["barcode"],
                    reference=row["product_code"],
                    detail_path=f"/products/{row['product_code']}",
                )
                for row in await self._rows(
                    """
                    SELECT id, product_code, name, sku, barcode
                    FROM products
                    WHERE tenant_id = :tenant_id
                      AND archived = false
                      AND (
                        lower(name) LIKE :term ESCAPE '\\'
                        OR lower(product_code) LIKE :term ESCAPE '\\'
                        OR lower(COALESCE(sku, '')) LIKE :term ESCAPE '\\'
                        OR lower(COALESCE(barcode, '')) LIKE :term ESCAPE '\\'
                      )
                    ORDER BY lower(name), id
                    LIMIT :limit
                    """,
                    params,
                )
            ],
            sales=[
                GlobalSearchItemResponse(
                    id=row["id"],
                    type="sale",
                    title=row["sale_number"],
                    subtitle=row["customer_name"],
                    reference=row["status"],
                    detail_path=f"/sales/{row['sale_number']}",
                )
                for row in await self._rows(
                    """
                    SELECT sale.id, sale.sale_number, sale.status, customer.name AS customer_name
                    FROM sales sale
                    JOIN customers customer
                      ON customer.tenant_id = sale.tenant_id
                     AND customer.id = sale.customer_id
                    WHERE sale.tenant_id = :tenant_id
                      AND (
                        lower(sale.sale_number) LIKE :term ESCAPE '\\'
                        OR lower(customer.name) LIKE :term ESCAPE '\\'
                      )
                    ORDER BY sale.created_at DESC, sale.id DESC
                    LIMIT :limit
                    """,
                    params,
                )
            ],
            invoices=[
                GlobalSearchItemResponse(
                    id=row["id"],
                    type="invoice",
                    title=row["invoice_number"],
                    subtitle=row["customer_name_snapshot"],
                    reference=row["status"],
                    detail_path=f"/invoices/{row['invoice_number']}",
                )
                for row in await self._rows(
                    """
                    SELECT id, invoice_number, customer_name_snapshot, status
                    FROM invoices
                    WHERE tenant_id = :tenant_id
                      AND (
                        lower(invoice_number) LIKE :term ESCAPE '\\'
                        OR lower(sale_number_snapshot) LIKE :term ESCAPE '\\'
                        OR lower(customer_name_snapshot) LIKE :term ESCAPE '\\'
                      )
                    ORDER BY created_at DESC, id DESC
                    LIMIT :limit
                    """,
                    params,
                )
            ],
            payments=[
                GlobalSearchItemResponse(
                    id=row["id"],
                    type="payment",
                    title=row["payment_number"],
                    subtitle=row["customer_name"],
                    reference=row["status"],
                    detail_path=f"/payments/{row['payment_number']}",
                )
                for row in await self._rows(
                    """
                    SELECT payment.id, payment.payment_number, payment.status,
                           customer.name AS customer_name
                    FROM payments payment
                    JOIN customers customer
                      ON customer.tenant_id = payment.tenant_id
                     AND customer.id = payment.customer_id
                    WHERE payment.tenant_id = :tenant_id
                      AND (
                        lower(payment.payment_number) LIKE :term ESCAPE '\\'
                        OR lower(COALESCE(payment.reference_number, '')) LIKE :term ESCAPE '\\'
                        OR lower(customer.name) LIKE :term ESCAPE '\\'
                      )
                    ORDER BY payment.created_at DESC, payment.id DESC
                    LIMIT :limit
                    """,
                    params,
                )
            ],
            inventory=[
                GlobalSearchItemResponse(
                    id=row["product_id"],
                    type="inventory",
                    title=row["product_name"],
                    subtitle=f"{row['current_stock']} {row['unit']}",
                    reference=row["product_code"],
                    detail_path=f"/inventory/{row['product_code']}",
                )
                for row in await self._rows(
                    """
                    SELECT product.id AS product_id, product.product_code,
                           product.name AS product_name, product.unit,
                           COALESCE(SUM(balance.available_quantity), 0) AS current_stock
                    FROM products product
                    LEFT JOIN stock_balances balance
                      ON balance.tenant_id = product.tenant_id
                     AND balance.product_id = product.id
                    WHERE product.tenant_id = :tenant_id
                      AND product.archived = false
                      AND (
                        lower(product.name) LIKE :term ESCAPE '\\'
                        OR lower(product.product_code) LIKE :term ESCAPE '\\'
                        OR lower(COALESCE(product.sku, '')) LIKE :term ESCAPE '\\'
                        OR lower(COALESCE(product.barcode, '')) LIKE :term ESCAPE '\\'
                      )
                    GROUP BY product.id, product.product_code, product.name, product.unit
                    ORDER BY lower(product.name), product.id
                    LIMIT :limit
                    """,
                    params,
                )
            ],
        )

    async def sales_report(
        self,
        tenant_id: UUID,
        *,
        period: ReportPeriod,
        date_from: date | None,
        date_to: date | None,
        status: ReportStatusFilter,
        search: str | None,
        sort: SalesReportSort,
        limit: int,
        cursor: str | None,
    ) -> SalesReportResponse:
        page_limit = self._limit(limit)
        timezone = await self._business_timezone(tenant_id)
        date_range = self._date_range(period, date_from, date_to, timezone)
        cursor_payload = self._decode_cursor(
            cursor,
            report="sales",
            params={
                "period": period,
                "date_from": str(date_range.date_from),
                "date_to": str(date_range.date_to),
                "status": status,
                "search": search or "",
                "sort": sort,
            },
        )
        rows = await self._sales_rows(
            tenant_id,
            date_range=date_range,
            status=status,
            search=search,
            sort=sort,
            limit=page_limit + 1,
            cursor_payload=cursor_payload,
            timezone=timezone,
        )
        items = [self._sales_row(row) for row in rows[:page_limit]]
        return SalesReportResponse(
            currency=await self._business_currency(tenant_id),
            items=items,
            next_cursor=self._next_cursor(
                "sales",
                sort,
                rows,
                page_limit,
                {
                    "period": period,
                    "date_from": str(date_range.date_from),
                    "date_to": str(date_range.date_to),
                    "status": status,
                    "search": search or "",
                    "sort": sort,
                },
            ),
        )

    async def payments_report(
        self,
        tenant_id: UUID,
        *,
        period: ReportPeriod,
        date_from: date | None,
        date_to: date | None,
        status: ReportStatusFilter,
        search: str | None,
        sort: PaymentReportSort,
        limit: int,
        cursor: str | None,
    ) -> PaymentReportResponse:
        page_limit = self._limit(limit)
        timezone = await self._business_timezone(tenant_id)
        date_range = self._date_range(period, date_from, date_to, timezone)
        cursor_payload = self._decode_cursor(
            cursor,
            report="payments",
            params={
                "period": period,
                "date_from": str(date_range.date_from),
                "date_to": str(date_range.date_to),
                "status": status,
                "search": search or "",
                "sort": sort,
            },
        )
        rows = await self._payment_rows(
            tenant_id,
            date_range=date_range,
            status=status,
            search=search,
            sort=sort,
            limit=page_limit + 1,
            cursor_payload=cursor_payload,
        )
        items = [self._payment_row(row) for row in rows[:page_limit]]
        return PaymentReportResponse(
            currency=await self._business_currency(tenant_id),
            items=items,
            next_cursor=self._next_cursor(
                "payments",
                sort,
                rows,
                page_limit,
                {
                    "period": period,
                    "date_from": str(date_range.date_from),
                    "date_to": str(date_range.date_to),
                    "status": status,
                    "search": search or "",
                    "sort": sort,
                },
            ),
        )

    async def outstanding_report(
        self,
        tenant_id: UUID,
        *,
        search: str | None,
        sort: OutstandingReportSort,
        limit: int,
        cursor: str | None,
    ) -> OutstandingReportResponse:
        page_limit = self._limit(limit)
        cursor_payload = self._decode_cursor(
            cursor,
            report="outstanding",
            params={"search": search or "", "sort": sort},
        )
        rows = await self._outstanding_rows(
            tenant_id,
            search=search,
            sort=sort,
            limit=page_limit + 1,
            cursor_payload=cursor_payload,
        )
        items = [self._outstanding_row(row) for row in rows[:page_limit]]
        return OutstandingReportResponse(
            currency=await self._business_currency(tenant_id),
            items=items,
            next_cursor=self._next_cursor(
                "outstanding",
                sort,
                rows,
                page_limit,
                {"search": search or "", "sort": sort},
            ),
        )

    async def inventory_report(
        self,
        tenant_id: UUID,
        *,
        search: str | None,
        sort: InventoryReportSort,
        limit: int,
        cursor: str | None,
    ) -> InventoryReportResponse:
        page_limit = self._limit(limit)
        cursor_payload = self._decode_cursor(
            cursor,
            report="inventory",
            params={"search": search or "", "sort": sort},
        )
        rows = await self._inventory_rows(
            tenant_id,
            search=search,
            sort=sort,
            limit=page_limit + 1,
            cursor_payload=cursor_payload,
            low_stock_only=False,
        )
        items = [self._inventory_row(row) for row in rows[:page_limit]]
        return InventoryReportResponse(
            currency=await self._business_currency(tenant_id),
            items=items,
            next_cursor=self._next_cursor(
                "inventory",
                sort,
                rows,
                page_limit,
                {"search": search or "", "sort": sort},
            ),
        )

    async def low_stock_report(
        self,
        tenant_id: UUID,
        *,
        search: str | None,
        sort: LowStockReportSort,
        limit: int,
        cursor: str | None,
    ) -> LowStockReportResponse:
        page_limit = self._limit(limit)
        cursor_payload = self._decode_cursor(
            cursor,
            report="low_stock",
            params={"search": search or "", "sort": sort},
        )
        inventory_sort: InventoryReportSort = "stock_asc" if sort == "lowest_stock" else "name_asc"
        rows = await self._inventory_rows(
            tenant_id,
            search=search,
            sort=inventory_sort,
            limit=page_limit + 1,
            cursor_payload=cursor_payload,
            low_stock_only=True,
        )
        items = [self._inventory_row(row) for row in rows[:page_limit]]
        return LowStockReportResponse(
            currency=await self._business_currency(tenant_id),
            items=items,
            next_cursor=self._next_cursor(
                "low_stock",
                inventory_sort,
                rows,
                page_limit,
                {"search": search or "", "sort": sort},
            ),
        )

    async def sales_csv(
        self,
        tenant_id: UUID,
        *,
        period: ReportPeriod,
        date_from: date | None,
        date_to: date | None,
        status: ReportStatusFilter,
        search: str | None,
        sort: SalesReportSort,
    ) -> CsvExport:
        timezone = await self._business_timezone(tenant_id)
        date_range = self._date_range(period, date_from, date_to, timezone)
        rows = await self._sales_rows(
            tenant_id,
            date_range=date_range,
            status=status,
            search=search,
            sort=sort,
            limit=CSV_EXPORT_LIMIT,
            cursor_payload=None,
            timezone=timezone,
        )
        currency = await self._business_currency(tenant_id)
        return self._csv(
            "sales-report.csv",
            [
                "Sale Number",
                "Customer",
                "Date",
                "Items",
                "Subtotal",
                "Total",
                "Currency",
                "Status",
            ],
            [
                [
                    row["sale_number"],
                    row["customer"],
                    row["sale_date"],
                    row["items"],
                    row["subtotal"],
                    row["total"],
                    currency,
                    row["status"],
                ]
                for row in rows
            ],
        )

    async def payments_csv(
        self,
        tenant_id: UUID,
        *,
        period: ReportPeriod,
        date_from: date | None,
        date_to: date | None,
        status: ReportStatusFilter,
        search: str | None,
        sort: PaymentReportSort,
    ) -> CsvExport:
        timezone = await self._business_timezone(tenant_id)
        date_range = self._date_range(period, date_from, date_to, timezone)
        rows = await self._payment_rows(
            tenant_id,
            date_range=date_range,
            status=status,
            search=search,
            sort=sort,
            limit=CSV_EXPORT_LIMIT,
            cursor_payload=None,
        )
        currency = await self._business_currency(tenant_id)
        return self._csv(
            "payments-report.csv",
            [
                "Payment Number",
                "Customer",
                "Date",
                "Amount",
                "Allocated",
                "Unallocated",
                "Currency",
                "Status",
            ],
            [
                [
                    row["payment_number"],
                    row["customer"],
                    row["payment_date"],
                    row["amount"],
                    row["allocated"],
                    row["unallocated"],
                    currency,
                    row["status"],
                ]
                for row in rows
            ],
        )

    async def outstanding_csv(
        self,
        tenant_id: UUID,
        *,
        search: str | None,
        sort: OutstandingReportSort,
    ) -> CsvExport:
        timezone = await self._business_timezone(tenant_id)
        rows = await self._outstanding_rows(
            tenant_id,
            search=search,
            sort=sort,
            limit=CSV_EXPORT_LIMIT,
            cursor_payload=None,
        )
        currency = await self._business_currency(tenant_id)
        return self._csv(
            "outstanding-customers-report.csv",
            [
                "Customer Code",
                "Customer",
                "Outstanding Balance",
                "Available Credit",
                "Currency",
                "Last Sale",
                "Last Payment",
            ],
            [
                [
                    row["customer_code"],
                    row["customer"],
                    row["outstanding_balance"],
                    row["available_credit"],
                    currency,
                    self._local_datetime(row["last_sale_at"], timezone),
                    self._local_datetime(row["last_payment_at"], timezone),
                ]
                for row in rows
            ],
        )

    async def inventory_csv(
        self,
        tenant_id: UUID,
        *,
        search: str | None,
        sort: InventoryReportSort,
    ) -> CsvExport:
        rows = await self._inventory_rows(
            tenant_id,
            search=search,
            sort=sort,
            limit=CSV_EXPORT_LIMIT,
            cursor_payload=None,
            low_stock_only=False,
        )
        return self._inventory_csv(
            "inventory-report.csv", rows, await self._business_currency(tenant_id)
        )

    async def low_stock_csv(
        self,
        tenant_id: UUID,
        *,
        search: str | None,
        sort: LowStockReportSort,
    ) -> CsvExport:
        inventory_sort: InventoryReportSort = "stock_asc" if sort == "lowest_stock" else "name_asc"
        rows = await self._inventory_rows(
            tenant_id,
            search=search,
            sort=inventory_sort,
            limit=CSV_EXPORT_LIMIT,
            cursor_payload=None,
            low_stock_only=True,
        )
        return self._inventory_csv(
            "low-stock-report.csv", rows, await self._business_currency(tenant_id)
        )

    async def _sales_rows(
        self,
        tenant_id: UUID,
        *,
        date_range: DateRange,
        status: ReportStatusFilter,
        search: str | None,
        sort: SalesReportSort,
        limit: int,
        cursor_payload: dict[str, Any] | None,
        timezone: str,
    ) -> list[RowMapping]:
        where = ["sale.tenant_id = :tenant_id"]
        params: dict[str, Any] = {
            "tenant_id": tenant_id,
            "timezone": timezone,
            "limit": limit,
        }
        if status != "all":
            if status not in {"draft", "posted", "void"}:
                raise self._invalid_filter("Sales status must be all, draft, posted, or void.")
            where.append("sale.status = :status")
            params["status"] = status.upper()
        self._apply_date_filters(where, params, "sale.created_at", date_range)
        self._apply_search(
            where,
            params,
            search,
            ["sale.sale_number", "customer.name"],
        )
        self._apply_report_cursor(where, params, sort, cursor_payload, "sale")
        order = {
            "newest": "sale.created_at DESC, sale.id DESC",
            "oldest": "sale.created_at ASC, sale.id ASC",
            "amount_desc": "sale.subtotal DESC, sale.id DESC",
            "amount_asc": "sale.subtotal ASC, sale.id ASC",
            "customer_asc": "lower(customer.name) ASC, sale.id ASC",
            "customer_desc": "lower(customer.name) DESC, sale.id DESC",
        }[sort]
        sql = f"""
            SELECT sale.id, sale.sale_number, customer.name AS customer,
                   DATE(sale.created_at AT TIME ZONE :timezone) AS sale_date,
                   COUNT(item.id)::int AS items,
                   sale.subtotal,
                   sale.subtotal AS total,
                   sale.status,
                   sale.created_at AS cursor_datetime,
                   sale.subtotal AS cursor_amount,
                   lower(customer.name) AS cursor_text,
                   sale.id AS cursor_id
            FROM sales sale
            JOIN customers customer
              ON customer.tenant_id = sale.tenant_id
             AND customer.id = sale.customer_id
            JOIN sale_items item
              ON item.sale_id = sale.id
            WHERE {" AND ".join(where)}
            GROUP BY sale.id, sale.sale_number, customer.name, sale.created_at,
                     sale.subtotal, sale.status
            ORDER BY {order}
            LIMIT :limit
            """  # noqa: S608 - order and where fragments are enum-selected.
        return await self._rows(sql, params)

    async def _payment_rows(
        self,
        tenant_id: UUID,
        *,
        date_range: DateRange,
        status: ReportStatusFilter,
        search: str | None,
        sort: PaymentReportSort,
        limit: int,
        cursor_payload: dict[str, Any] | None,
    ) -> list[RowMapping]:
        where = ["payment.tenant_id = :tenant_id"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}
        if status != "all":
            if status not in {"posted", "void"}:
                raise self._invalid_filter("Payment status must be all, posted, or void.")
            where.append("payment.status = :status")
            params["status"] = status.upper()
        if date_range.date_from is not None:
            where.append("payment.payment_date >= :date_from")
            params["date_from"] = date_range.date_from
        if date_range.date_to is not None:
            where.append("payment.payment_date <= :date_to")
            params["date_to"] = date_range.date_to
        self._apply_search(
            where,
            params,
            search,
            ["payment.payment_number", "payment.reference_number", "customer.name"],
        )
        self._apply_report_cursor(where, params, sort, cursor_payload, "payment")
        order = {
            "newest": "payment.payment_date DESC, payment.id DESC",
            "oldest": "payment.payment_date ASC, payment.id ASC",
            "amount_desc": "payment.amount DESC, payment.id DESC",
            "amount_asc": "payment.amount ASC, payment.id ASC",
            "customer_asc": "lower(customer.name) ASC, payment.id ASC",
            "customer_desc": "lower(customer.name) DESC, payment.id DESC",
        }[sort]
        sql = f"""
            WITH effective_allocations AS (
                SELECT allocation.payment_id,
                       COALESCE(SUM(allocation.allocated_amount), 0) AS allocated
                FROM payment_allocations allocation
                JOIN payments allocation_payment
                  ON allocation_payment.id = allocation.payment_id
                 AND allocation_payment.tenant_id = allocation.tenant_id
                 AND allocation_payment.status = 'POSTED'
                JOIN customer_ledger_entries target
                  ON target.id = allocation.ledger_entry_id
                 AND target.tenant_id = allocation.tenant_id
                LEFT JOIN invoices invoice
                  ON invoice.id = allocation.invoice_id
                 AND invoice.tenant_id = allocation.tenant_id
                WHERE allocation.tenant_id = :tenant_id
                  AND (allocation.invoice_id IS NULL OR invoice.status = 'ISSUED')
                  AND NOT EXISTS (
                      SELECT 1
                      FROM customer_ledger_entries reversal
                      WHERE reversal.tenant_id = target.tenant_id
                        AND reversal.customer_id = target.customer_id
                        AND reversal.reference_type = target.reference_type
                        AND reversal.reference_id = target.reference_id
                        AND reversal.entry_type IN ('REVERSAL', 'PAYMENT_REVERSAL')
                  )
                GROUP BY allocation.payment_id
            )
            SELECT payment.id, payment.payment_number, customer.name AS customer,
                   payment.payment_date, payment.amount,
                   CASE
                     WHEN payment.status = 'POSTED'
                     THEN COALESCE(effective_allocations.allocated, 0)
                     ELSE 0
                   END AS allocated,
                   CASE
                     WHEN payment.status = 'POSTED'
                     THEN GREATEST(
                        payment.amount - COALESCE(effective_allocations.allocated, 0),
                        0
                     )
                     ELSE 0
                   END AS unallocated,
                   payment.status,
                   payment.payment_date AS cursor_date,
                   payment.amount AS cursor_amount,
                   lower(customer.name) AS cursor_text,
                   payment.id AS cursor_id
            FROM payments payment
            JOIN customers customer
              ON customer.tenant_id = payment.tenant_id
             AND customer.id = payment.customer_id
            LEFT JOIN effective_allocations
              ON effective_allocations.payment_id = payment.id
            WHERE {" AND ".join(where)}
            ORDER BY {order}
            LIMIT :limit
            """  # noqa: S608 - order and where fragments are enum-selected.
        return await self._rows(sql, params)

    async def _outstanding_rows(
        self,
        tenant_id: UUID,
        *,
        search: str | None,
        sort: OutstandingReportSort,
        limit: int,
        cursor_payload: dict[str, Any] | None,
    ) -> list[RowMapping]:
        where = ["balance.tenant_id = :tenant_id", "balance.outstanding_balance > 0"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}
        self._apply_search(where, params, search, ["customer.name", "customer.customer_code"])
        self._apply_report_cursor(where, params, sort, cursor_payload, "outstanding")
        order = {
            "highest_outstanding": "balance.outstanding_balance DESC, customer.id DESC",
            "alphabetical": "lower(customer.name) ASC, customer.id ASC",
        }[sort]
        sql = f"""
            SELECT customer.id AS customer_id, customer.customer_code,
                   customer.name AS customer,
                   balance.outstanding_balance, balance.available_credit,
                   balance.last_sale_at, balance.last_payment_at,
                   balance.outstanding_balance AS cursor_amount,
                   lower(customer.name) AS cursor_text,
                   customer.id AS cursor_id
            FROM customer_balance_projections balance
            JOIN customers customer
              ON customer.tenant_id = balance.tenant_id
             AND customer.id = balance.customer_id
            WHERE {" AND ".join(where)}
            ORDER BY {order}
            LIMIT :limit
            """  # noqa: S608 - order and where fragments are enum-selected.
        return await self._rows(sql, params)

    async def _inventory_rows(
        self,
        tenant_id: UUID,
        *,
        search: str | None,
        sort: InventoryReportSort,
        limit: int,
        cursor_payload: dict[str, Any] | None,
        low_stock_only: bool,
    ) -> list[RowMapping]:
        where = ["product.tenant_id = :tenant_id", "product.archived = false"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}
        self._apply_search(
            where,
            params,
            search,
            ["product.name", "product.product_code", "product.sku", "product.barcode"],
        )
        stock_filter = "AND current_stock <= low_stock_threshold" if low_stock_only else ""
        self._apply_report_cursor(where, params, sort, cursor_payload, "inventory")
        order = {
            "name_asc": "lower(product_name) ASC, product_id ASC",
            "name_desc": "lower(product_name) DESC, product_id DESC",
            "stock_asc": "current_stock ASC, product_id ASC",
            "stock_desc": "current_stock DESC, product_id DESC",
            "value_asc": "inventory_value ASC, product_id ASC",
            "value_desc": "inventory_value DESC, product_id DESC",
        }[sort]
        sql = f"""
            WITH product_stock AS (
                SELECT product.id AS product_id, product.product_code,
                       product.name AS product_name, product.unit,
                       product.selling_price, product.low_stock_threshold,
                       COALESCE(SUM(balance.available_quantity), 0) AS current_stock
                FROM products product
                LEFT JOIN stock_balances balance
                  ON balance.tenant_id = product.tenant_id
                 AND balance.product_id = product.id
                WHERE {" AND ".join(where)}
                GROUP BY product.id, product.product_code, product.name, product.unit,
                         product.selling_price, product.low_stock_threshold
            )
            SELECT product_id, product_code, product_name AS product, current_stock,
                   unit, selling_price,
                   current_stock * selling_price AS inventory_value,
                   CASE
                     WHEN current_stock <= 0 THEN 'out'
                     WHEN current_stock <= low_stock_threshold THEN 'low'
                     ELSE 'ok'
                   END AS low_stock_status,
                   current_stock AS cursor_stock,
                   current_stock * selling_price AS cursor_amount,
                   lower(product_name) AS cursor_text,
                   product_id AS cursor_id
            FROM product_stock
            WHERE 1 = 1
            {stock_filter}
            ORDER BY {order}
            LIMIT :limit
            """  # noqa: S608 - order, filters, and where fragments are enum-selected.
        return await self._rows(sql, params)

    def _sales_row(self, row: RowMapping) -> SalesReportRowResponse:
        return SalesReportRowResponse(
            id=row["id"],
            sale_number=row["sale_number"],
            customer=row["customer"],
            sale_date=row["sale_date"],
            items=row["items"],
            subtotal=row["subtotal"],
            total=row["total"],
            status=row["status"],
        )

    def _payment_row(self, row: RowMapping) -> PaymentReportRowResponse:
        return PaymentReportRowResponse(
            id=row["id"],
            payment_number=row["payment_number"],
            customer=row["customer"],
            payment_date=row["payment_date"],
            amount=row["amount"],
            allocated=row["allocated"],
            unallocated=row["unallocated"],
            status=row["status"],
        )

    def _outstanding_row(self, row: RowMapping) -> OutstandingReportRowResponse:
        return OutstandingReportRowResponse(
            customer_id=row["customer_id"],
            customer_code=row["customer_code"],
            customer=row["customer"],
            outstanding_balance=row["outstanding_balance"],
            available_credit=row["available_credit"],
            last_sale_at=row["last_sale_at"],
            last_payment_at=row["last_payment_at"],
        )

    def _inventory_row(self, row: RowMapping) -> InventoryReportRowResponse:
        return InventoryReportRowResponse(
            product_id=row["product_id"],
            product_code=row["product_code"],
            product=row["product"],
            current_stock=row["current_stock"],
            unit=row["unit"],
            selling_price=row["selling_price"],
            inventory_value=row["inventory_value"],
            low_stock_status=row["low_stock_status"],
        )

    def _inventory_csv(self, filename: str, rows: list[RowMapping], currency: str) -> CsvExport:
        return self._csv(
            filename,
            [
                "Product Code",
                "Product",
                "Current Stock",
                "Unit",
                "Selling Price",
                "Inventory Value",
                "Currency",
                "Low Stock Status",
            ],
            [
                [
                    row["product_code"],
                    row["product"],
                    row["current_stock"],
                    row["unit"],
                    row["selling_price"],
                    row["inventory_value"],
                    currency,
                    row["low_stock_status"],
                ]
                for row in rows
            ],
        )

    async def _rows(self, sql: str, params: dict[str, Any]) -> list[RowMapping]:
        return list((await self.session.execute(text(sql), params)).mappings().all())

    async def _business_currency(self, tenant_id: UUID) -> str:
        currency = await self.session.scalar(
            text("SELECT currency FROM businesses WHERE id = :tenant_id"),
            {"tenant_id": tenant_id},
        )
        return str(currency or "INR")

    async def _business_timezone(self, tenant_id: UUID) -> str:
        timezone = await self.session.scalar(
            text("SELECT timezone FROM businesses WHERE id = :tenant_id"),
            {"tenant_id": tenant_id},
        )
        return str(timezone or DEFAULT_BUSINESS_TIMEZONE)

    def _date_range(
        self,
        period: ReportPeriod,
        date_from: date | None,
        date_to: date | None,
        timezone: str,
    ) -> DateRange:
        today = self._today(timezone)
        if period == "all":
            return DateRange(date_from=date_from, date_to=date_to)
        if period == "today":
            return DateRange(today, today)
        if period == "yesterday":
            yesterday = today - timedelta(days=1)
            return DateRange(yesterday, yesterday)
        if period == "this_week":
            return DateRange(today - timedelta(days=today.weekday()), today)
        if period == "this_month":
            return DateRange(today.replace(day=1), today)
        if date_from is None or date_to is None:
            raise self._invalid_filter(
                "Choose both a start date and end date for a custom report range."
            )
        if date_from > date_to:
            raise self._invalid_filter("Start date must be before or equal to end date.")
        return DateRange(date_from, date_to)

    def _apply_date_filters(
        self, where: list[str], params: dict[str, Any], column: str, date_range: DateRange
    ) -> None:
        if date_range.date_from is not None:
            where.append(f"DATE({column} AT TIME ZONE :timezone) >= :date_from")
            params["date_from"] = date_range.date_from
        if date_range.date_to is not None:
            where.append(f"DATE({column} AT TIME ZONE :timezone) <= :date_to")
            params["date_to"] = date_range.date_to

    def _apply_search(
        self,
        where: list[str],
        params: dict[str, Any],
        search: str | None,
        columns: list[str],
    ) -> None:
        if search and search.strip():
            params["search"] = self._search_term(search)
            where.append(
                "("
                + " OR ".join(
                    f"lower(COALESCE({column}, '')) LIKE :search ESCAPE '\\'" for column in columns
                )
                + ")"
            )

    def _apply_report_cursor(
        self,
        where: list[str],
        params: dict[str, Any],
        sort: str,
        cursor_payload: dict[str, Any] | None,
        prefix: str,
    ) -> None:
        if cursor_payload is None:
            return
        last = cursor_payload["last"]
        params["cursor_id"] = UUID(last["id"])
        if sort in {"newest", "oldest"} and prefix == "sale":
            params["cursor_datetime"] = datetime.fromisoformat(last["datetime"])
            where.append(
                "(sale.created_at, sale.id) "
                + ("<" if sort == "newest" else ">")
                + " (:cursor_datetime, :cursor_id)"
            )
            return
        if sort in {"newest", "oldest"} and prefix == "payment":
            params["cursor_date"] = date.fromisoformat(last["date"])
            where.append(
                "(payment.payment_date, payment.id) "
                + ("<" if sort == "newest" else ">")
                + " (:cursor_date, :cursor_id)"
            )
            return
        if sort in {"amount_desc", "amount_asc"}:
            params["cursor_amount"] = Decimal(last["amount"])
            if prefix == "sale":
                condition = (
                    "(sale.subtotal, sale.id) < (:cursor_amount, :cursor_id)"
                    if sort == "amount_desc"
                    else "(sale.subtotal, sale.id) > (:cursor_amount, :cursor_id)"
                )
            else:
                condition = (
                    "(payment.amount, payment.id) < (:cursor_amount, :cursor_id)"
                    if sort == "amount_desc"
                    else "(payment.amount, payment.id) > (:cursor_amount, :cursor_id)"
                )
            where.append(condition)
            return
        if sort in {"customer_asc", "customer_desc"}:
            params["cursor_text"] = last["text"]
            if prefix == "sale":
                condition = (
                    "(lower(customer.name), sale.id) > (:cursor_text, :cursor_id)"
                    if sort == "customer_asc"
                    else "(lower(customer.name), sale.id) < (:cursor_text, :cursor_id)"
                )
            else:
                condition = (
                    "(lower(customer.name), payment.id) > (:cursor_text, :cursor_id)"
                    if sort == "customer_asc"
                    else "(lower(customer.name), payment.id) < (:cursor_text, :cursor_id)"
                )
            where.append(condition)
            return
        if prefix == "outstanding" and sort == "highest_outstanding":
            params["cursor_amount"] = Decimal(last["amount"])
            where.append(
                "(balance.outstanding_balance, customer.id) < (:cursor_amount, :cursor_id)"
            )
            return
        if prefix == "outstanding" and sort == "alphabetical":
            params["cursor_text"] = last["text"]
            where.append("(lower(customer.name), customer.id) > (:cursor_text, :cursor_id)")
            return
        if prefix == "inventory":
            if sort in {"name_asc", "name_desc"}:
                params["cursor_text"] = last["text"]
                where.append(
                    "(lower(product.name), product.id) "
                    + (">" if sort == "name_asc" else "<")
                    + " (:cursor_text, :cursor_id)"
                )
            elif sort in {"stock_asc", "stock_desc"}:
                params["cursor_stock"] = Decimal(last["stock"])
                if sort == "stock_asc":
                    where.append(
                        "product.id IN ("
                        "SELECT filtered.product_id FROM ("
                        "SELECT product_cursor.id AS product_id, "
                        "COALESCE(SUM(balance_cursor.available_quantity), 0) "
                        "AS cursor_stock "
                        "FROM products product_cursor "
                        "LEFT JOIN stock_balances balance_cursor "
                        "ON balance_cursor.tenant_id = product_cursor.tenant_id "
                        "AND balance_cursor.product_id = product_cursor.id "
                        "WHERE product_cursor.tenant_id = :tenant_id "
                        "GROUP BY product_cursor.id"
                        ") filtered "
                        "WHERE (filtered.cursor_stock, filtered.product_id) "
                        "> (:cursor_stock, :cursor_id))"
                    )
                else:
                    where.append(
                        "product.id IN ("
                        "SELECT filtered.product_id FROM ("
                        "SELECT product_cursor.id AS product_id, "
                        "COALESCE(SUM(balance_cursor.available_quantity), 0) "
                        "AS cursor_stock "
                        "FROM products product_cursor "
                        "LEFT JOIN stock_balances balance_cursor "
                        "ON balance_cursor.tenant_id = product_cursor.tenant_id "
                        "AND balance_cursor.product_id = product_cursor.id "
                        "WHERE product_cursor.tenant_id = :tenant_id "
                        "GROUP BY product_cursor.id"
                        ") filtered "
                        "WHERE (filtered.cursor_stock, filtered.product_id) "
                        "< (:cursor_stock, :cursor_id))"
                    )
            elif sort in {"value_asc", "value_desc"}:
                params["cursor_amount"] = Decimal(last["amount"])
                if sort == "value_asc":
                    where.append(
                        "product.id IN ("
                        "SELECT filtered.product_id FROM ("
                        "SELECT product_cursor.id AS product_id, "
                        "COALESCE(SUM(balance_cursor.available_quantity), 0) "
                        "* product_cursor.selling_price AS cursor_value "
                        "FROM products product_cursor "
                        "LEFT JOIN stock_balances balance_cursor "
                        "ON balance_cursor.tenant_id = product_cursor.tenant_id "
                        "AND balance_cursor.product_id = product_cursor.id "
                        "WHERE product_cursor.tenant_id = :tenant_id "
                        "GROUP BY product_cursor.id, product_cursor.selling_price"
                        ") filtered "
                        "WHERE (filtered.cursor_value, filtered.product_id) "
                        "> (:cursor_amount, :cursor_id))"
                    )
                else:
                    where.append(
                        "product.id IN ("
                        "SELECT filtered.product_id FROM ("
                        "SELECT product_cursor.id AS product_id, "
                        "COALESCE(SUM(balance_cursor.available_quantity), 0) "
                        "* product_cursor.selling_price AS cursor_value "
                        "FROM products product_cursor "
                        "LEFT JOIN stock_balances balance_cursor "
                        "ON balance_cursor.tenant_id = product_cursor.tenant_id "
                        "AND balance_cursor.product_id = product_cursor.id "
                        "WHERE product_cursor.tenant_id = :tenant_id "
                        "GROUP BY product_cursor.id, product_cursor.selling_price"
                        ") filtered "
                        "WHERE (filtered.cursor_value, filtered.product_id) "
                        "< (:cursor_amount, :cursor_id))"
                    )

    def _next_cursor(
        self,
        report: str,
        sort: str,
        rows: list[RowMapping],
        page_limit: int,
        params: dict[str, str],
    ) -> str | None:
        if len(rows) <= page_limit:
            return None
        last = rows[page_limit - 1]
        payload: dict[str, Any] = {
            "version": 1,
            "report": report,
            "sort": sort,
            "params": params,
            "last": {"id": str(last["cursor_id"])},
        }
        if "cursor_datetime" in last:
            payload["last"]["datetime"] = last["cursor_datetime"].isoformat()
        if "cursor_date" in last:
            payload["last"]["date"] = last["cursor_date"].isoformat()
        if "cursor_amount" in last:
            payload["last"]["amount"] = str(last["cursor_amount"])
        if "cursor_stock" in last:
            payload["last"]["stock"] = str(last["cursor_stock"])
        if "cursor_text" in last:
            payload["last"]["text"] = last["cursor_text"]
        encoded = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode())
        return encoded.decode().rstrip("=")

    def _decode_cursor(
        self, cursor: str | None, *, report: str, params: dict[str, str]
    ) -> dict[str, Any] | None:
        if not cursor:
            return None
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload: dict[str, Any] = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
            if (
                payload.get("version") != 1
                or payload.get("report") != report
                or payload.get("params") != params
            ):
                raise ValueError
            return payload
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise AppError(
                status_code=422,
                code="INVALID_REPORT_CURSOR",
                message=(
                    "The report page token is no longer valid. Refresh the report and try again."
                ),
                field_errors={"cursor": "Refresh the report before loading more rows."},
            ) from exc

    def _csv(self, filename: str, headers: list[str], rows: list[list[Any]]) -> CsvExport:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(headers)
        for row in rows:
            writer.writerow([self._csv_value(value) for value in row])
        return CsvExport(filename=filename, content="\ufeff" + buffer.getvalue())

    def _csv_value(self, value: Any) -> str:
        if value is None:
            return ""
        text_value = str(value)
        if text_value.startswith(("=", "+", "-", "@")):
            return "'" + text_value
        return text_value

    def _metric(
        self, label: str, value: Decimal | int, unit: Literal["money", "count"]
    ) -> DashboardMetricResponse:
        amount = Decimal(str(value))
        if unit == "money":
            amount = amount.quantize(Decimal("0.01"))
        return DashboardMetricResponse(label=label, value=amount, unit=unit)

    def _limit(self, value: int, *, default: int = DEFAULT_LIMIT, maximum: int = MAX_LIMIT) -> int:
        if value <= 0:
            return default
        return min(value, maximum)

    def _search_term(self, value: str) -> str:
        escaped = (
            value.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        return f"%{escaped}%"

    @staticmethod
    def _today(timezone: str) -> date:
        return datetime.now(ZoneInfo(timezone)).date()

    @staticmethod
    def _local_datetime(value: datetime | None, timezone: str) -> str:
        if value is None:
            return ""
        return value.astimezone(ZoneInfo(timezone)).isoformat()

    def _invalid_filter(self, message: str) -> AppError:
        return AppError(
            status_code=422,
            code="REPORT_FILTER_INVALID",
            message=message,
            field_errors={"filters": "Adjust the report filters and try again."},
        )
