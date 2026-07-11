from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.errors import AppError
from distributoros.modules.customers.models import Customer
from distributoros.modules.inventory.models import StockMovement, Warehouse
from distributoros.modules.inventory.repository import InventoryRepository
from distributoros.modules.ledger.service import FinancialPostingService
from distributoros.modules.products.models import Product
from distributoros.modules.sales.models import Sale, SaleItem
from distributoros.modules.sales.repository import SaleDetails, SalePage, SalesRepository
from distributoros.modules.sales.schemas import (
    SaleCreateRequest,
    SaleItemRequest,
    SaleSort,
    SaleStatusFilter,
    SaleUpdateRequest,
)
from distributoros.modules.tenancy.models import Business


@dataclass(frozen=True)
class CalculatedLine:
    request: SaleItemRequest
    product: Product
    line_total: Decimal


class SalesService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SalesRepository(session)
        self.inventory = InventoryRepository(session)
        self.financial_posting = FinancialPostingService(session)
        self.logger = structlog.get_logger("distributoros.sales")

    async def create(
        self,
        request: SaleCreateRequest,
        *,
        idempotency_key: str | None,
        tenant_id: UUID,
        user_id: UUID,
    ) -> SaleDetails:
        key = self._idempotency_key(idempotency_key)
        request_hash = self._request_hash(request)
        customer = await self._require_customer(tenant_id, request.customer_id)
        lines = await self._calculate_lines(tenant_id, request.items)
        sale: Sale | None = None
        try:
            async with self.session.begin_nested():
                sale = Sale(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    sale_number=await self.repository.next_sale_number(tenant_id),
                    customer_id=customer.id,
                    status="DRAFT",
                    subtotal=sum((line.line_total for line in lines), Decimal("0.00")),
                    created_by=user_id,
                    updated_at=datetime.now(UTC),
                    create_idempotency_key=key,
                    create_request_hash=request_hash,
                )
                self.repository.add_sale(sale)
                await self.session.flush()
                self.repository.add_items(self._items_for_sale(sale.id, lines))
                await self.session.flush()
        except IntegrityError as exc:
            if _constraint_name(exc) == "uq_sales_tenant_create_idempotency":
                existing = await self.repository.get_by_create_key(tenant_id, key)
                if existing is None:
                    raise
                if existing.create_request_hash != request_hash:
                    raise self._idempotency_reused() from exc
                return await self.repository.details(tenant_id, existing)
            raise
        if sale is None:
            raise RuntimeError("Sale creation did not produce a sale.")
        details = await self.repository.details(tenant_id, sale)
        self.logger.info(
            "sale_draft_created",
            tenant_id=str(tenant_id),
            sale_id=str(sale.id),
            sale_number=sale.sale_number,
            user_id=str(user_id),
        )
        return details

    async def get(self, sale_id: UUID, *, tenant_id: UUID) -> SaleDetails:
        sale = self._require_sale(await self.repository.get(tenant_id, sale_id))
        return await self.repository.details(tenant_id, sale)

    async def get_by_number(self, sale_number: str, *, tenant_id: UUID) -> SaleDetails:
        sale = self._require_sale(await self.repository.get_by_number(tenant_id, sale_number))
        return await self.repository.details(tenant_id, sale)

    async def update(
        self,
        sale_id: UUID,
        request: SaleUpdateRequest,
        *,
        tenant_id: UUID,
        user_id: UUID,
    ) -> SaleDetails:
        if request.customer_id is None and request.items is None:
            raise AppError(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Change the customer or at least one sale item before saving.",
                field_errors={"sale": "Update the customer or sale items and try again."},
            )
        sale = self._require_sale(await self.repository.get_for_update(tenant_id, sale_id))
        self._require_draft(sale)
        if (
            request.expected_updated_at is not None
            and sale.updated_at != request.expected_updated_at
        ):
            raise AppError(
                status_code=409,
                code="SALE_EDIT_CONFLICT",
                message=(
                    "This draft was changed in another tab or session. "
                    "Reload it before applying your changes."
                ),
                field_errors={
                    "sale": "Reload the latest draft, review the changes, and try again."
                },
            )
        if request.customer_id is not None:
            sale.customer_id = (await self._require_customer(tenant_id, request.customer_id)).id
        if request.items is not None:
            lines = await self._calculate_lines(tenant_id, request.items)
            sale.subtotal = sum((line.line_total for line in lines), Decimal("0.00"))
            await self.repository.replace_items(sale.id, self._items_for_sale(sale.id, lines))
        sale.updated_at = datetime.now(UTC)
        await self.session.flush()
        details = await self.repository.details(tenant_id, sale)
        self.logger.info(
            "sale_draft_updated",
            tenant_id=str(tenant_id),
            sale_id=str(sale.id),
            user_id=str(user_id),
        )
        return details

    async def post(
        self,
        sale_id: UUID,
        *,
        idempotency_key: str | None,
        tenant_id: UUID,
        user_id: UUID,
    ) -> SaleDetails:
        key = self._idempotency_key(idempotency_key)
        try:
            async with self.session.begin_nested():
                details = await self._post_once(
                    sale_id,
                    key=key,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
        except IntegrityError as exc:
            if _constraint_name(exc) == "uq_sales_tenant_post_idempotency":
                raise self._idempotency_reused() from exc
            raise
        return details

    async def _post_once(
        self,
        sale_id: UUID,
        *,
        key: str,
        tenant_id: UUID,
        user_id: UUID,
    ) -> SaleDetails:
        sale = self._require_sale(await self.repository.get_for_update(tenant_id, sale_id))
        if sale.status == "POSTED":
            if sale.post_idempotency_key == key:
                await self.financial_posting.validate_posted_sale(sale)
                return await self.repository.details(tenant_id, sale)
            raise AppError(
                status_code=409,
                code="SALE_ALREADY_POSTED",
                message="This sale has already been posted and cannot be posted again.",
            )
        if sale.status == "VOID":
            raise AppError(
                status_code=409,
                code="SALE_ALREADY_VOIDED",
                message="This sale has already been voided and cannot be posted.",
            )
        await self._require_customer(tenant_id, sale.customer_id)
        items = await self.repository.get_items(sale.id)
        if not items:
            raise AppError(
                status_code=409,
                code="SALE_ITEMS_REQUIRED",
                message="Add at least one product before posting this sale.",
            )
        products = await self._active_product_map(tenant_id, {item.product_id for item in items})
        for item in items:
            product = products[item.product_id]
            item.product_name_snapshot = product.name
            item.unit_snapshot = product.unit
        await self.session.flush()

        warehouse = await self._default_warehouse(tenant_id)
        ordered_items = sorted(items, key=lambda item: str(item.product_id))
        movements: list[StockMovement] = []
        for item in ordered_items:
            movements.append(
                self._sale_movement(
                    sale=sale,
                    item=item,
                    warehouse=warehouse,
                    user_id=user_id,
                )
            )
        self.session.add_all(movements)
        await self.session.flush()
        for item in ordered_items:
            balance = await self.inventory.apply_delta(
                tenant_id=tenant_id,
                product_id=item.product_id,
                warehouse_id=warehouse.id,
                delta=-item.quantity,
            )
            if balance is None:
                stock = await self.inventory.get_stock(
                    tenant_id=tenant_id,
                    product_id=item.product_id,
                    warehouse_id=warehouse.id,
                )
                available = stock.available_quantity if stock else Decimal("0.000")
                product = products[item.product_id]
                message = (
                    f"Only {_decimal_text(available)} {product.unit} available "
                    f"for {product.name}. Reduce the quantity and try again."
                )
                raise AppError(
                    status_code=409,
                    code="INSUFFICIENT_STOCK",
                    message=message,
                    field_errors={f"items.{item.product_id}.quantity": message},
                )
        await self.financial_posting.post_sale(sale, user_id=user_id)
        sale.status = "POSTED"
        sale.post_idempotency_key = key
        sale.updated_at = datetime.now(UTC)
        await self.session.flush()
        details = await self.repository.details(tenant_id, sale)
        self.logger.info(
            "sale_posted",
            tenant_id=str(tenant_id),
            sale_id=str(sale.id),
            sale_number=sale.sale_number,
            user_id=str(user_id),
        )
        return details

    async def void(
        self,
        sale_id: UUID,
        *,
        idempotency_key: str | None,
        tenant_id: UUID,
        user_id: UUID,
        allow_invoiced: bool = False,
    ) -> SaleDetails:
        key = self._idempotency_key(idempotency_key)
        try:
            async with self.session.begin_nested():
                details = await self._void_once(
                    sale_id,
                    key=key,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    allow_invoiced=allow_invoiced,
                )
        except IntegrityError as exc:
            if _constraint_name(exc) == "uq_sales_tenant_void_idempotency":
                raise self._idempotency_reused() from exc
            raise
        return details

    async def _void_once(
        self,
        sale_id: UUID,
        *,
        key: str,
        tenant_id: UUID,
        user_id: UUID,
        allow_invoiced: bool,
    ) -> SaleDetails:
        sale = self._require_sale(await self.repository.get_for_update(tenant_id, sale_id))
        if sale.status == "VOID":
            if sale.void_idempotency_key == key:
                await self.financial_posting.validate_voided_sale(sale)
                return await self.repository.details(tenant_id, sale)
            raise AppError(
                status_code=409,
                code="SALE_ALREADY_VOIDED",
                message="This sale has already been voided and cannot be voided again.",
            )
        if sale.status == "DRAFT":
            raise AppError(
                status_code=409,
                code="SALE_NOT_POSTED",
                message="Only a posted sale can be voided. Post this sale first.",
            )
        if not allow_invoiced and await self.repository.has_issued_invoice(tenant_id, sale.id):
            raise AppError(
                status_code=409,
                code="SALE_HAS_ISSUED_INVOICE",
                message=(
                    "This sale has an issued invoice. Void the invoice instead so the "
                    "invoice, inventory, and ledger stay consistent."
                ),
                field_errors={"sale_id": "Open the invoice for this sale and void it from there."},
            )
        await self.financial_posting.validate_can_void(sale)
        items = await self.repository.get_items(sale.id)
        original = await self.repository.sale_movements(tenant_id, sale.id)
        item_by_product = {item.product_id: item for item in items}
        history_valid = len(original) == len(items) and all(
            movement.product_id in item_by_product
            and movement.quantity == -item_by_product[movement.product_id].quantity
            and movement.unit == item_by_product[movement.product_id].unit_snapshot
            for movement in original
        )
        if not history_valid:
            raise AppError(
                status_code=409,
                code="SALE_INVENTORY_HISTORY_MISSING",
                message=(
                    "This sale's inventory history is incomplete. "
                    "Run inventory reconciliation before voiding it."
                ),
            )
        missing_projections = await self.repository.missing_stock_projections(
            tenant_id,
            {(movement.product_id, movement.warehouse_id) for movement in original},
        )
        if missing_projections:
            raise AppError(
                status_code=409,
                code="SALE_INVENTORY_PROJECTION_MISSING",
                message=(
                    "This sale cannot be voided because an inventory projection is missing. "
                    "Run inventory reconciliation and rebuild projections before trying again."
                ),
            )
        reversals = [
            self._void_movement(sale=sale, original=movement, user_id=user_id)
            for movement in original
        ]
        self.session.add_all(reversals)
        await self.session.flush()
        for movement in original:
            await self.inventory.apply_delta(
                tenant_id=tenant_id,
                product_id=movement.product_id,
                warehouse_id=movement.warehouse_id,
                delta=-movement.quantity,
            )
        await self.financial_posting.void_sale(sale, user_id=user_id)
        sale.status = "VOID"
        sale.void_idempotency_key = key
        sale.updated_at = datetime.now(UTC)
        await self.session.flush()
        details = await self.repository.details(tenant_id, sale)
        self.logger.info(
            "sale_voided",
            tenant_id=str(tenant_id),
            sale_id=str(sale.id),
            sale_number=sale.sale_number,
            user_id=str(user_id),
        )
        return details

    async def list_sales(
        self,
        *,
        tenant_id: UUID,
        sale_status: SaleStatusFilter,
        sale_sort: SaleSort,
        search: str | None,
        sale_date: date | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[SalePage, str | None]:
        timezone = await self.session.scalar(
            select(Business.timezone).where(Business.id == tenant_id)
        )
        date_from, date_to = _date_range(sale_date, str(timezone or "Asia/Kolkata"))
        cursor_created, cursor_id = self._decode_cursor(
            cursor,
            sale_status=sale_status,
            sale_sort=sale_sort,
            search=search,
            sale_date=sale_date,
        )
        page = await self.repository.list_sales(
            tenant_id=tenant_id,
            sale_status=sale_status,
            sale_sort=sale_sort,
            search=search,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            cursor_created_at=cursor_created,
            cursor_id=cursor_id,
        )
        next_cursor = None
        if page.has_more and page.items:
            last = page.items[-1].sale
            next_cursor = self._encode_cursor(
                created_at=last.created_at,
                sale_id=last.id,
                sale_status=sale_status,
                sale_sort=sale_sort,
                search=search,
                sale_date=sale_date,
            )
        return page, next_cursor

    async def _require_customer(self, tenant_id: UUID, customer_id: UUID) -> Customer:
        customer = await self.repository.get_customer(tenant_id, customer_id)
        if customer is None:
            raise AppError(
                status_code=404,
                code="CUSTOMER_NOT_FOUND",
                message="Selected customer was not found. Refresh customers and try again.",
                field_errors={"customer_id": "Select a customer from this business."},
            )
        if customer.archived:
            raise AppError(
                status_code=422,
                code="CUSTOMER_ARCHIVED",
                message="Customer has been archived. Restore the customer before creating a sale.",
                field_errors={"customer_id": "Customer has been archived."},
            )
        return customer

    async def _calculate_lines(
        self, tenant_id: UUID, requests: list[SaleItemRequest]
    ) -> list[CalculatedLine]:
        product_ids = [item.product_id for item in requests]
        if len(product_ids) != len(set(product_ids)):
            raise AppError(
                status_code=422,
                code="DUPLICATE_SALE_PRODUCT",
                message=(
                    "Each product can appear only once in a sale. Combine duplicate quantities."
                ),
                field_errors={"items": "Remove duplicate products and try again."},
            )
        products = await self._active_product_map(tenant_id, set(product_ids))
        return [
            CalculatedLine(
                request=item,
                product=products[item.product_id],
                line_total=(item.quantity * item.unit_price).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
            )
            for item in requests
        ]

    async def _active_product_map(
        self, tenant_id: UUID, product_ids: set[UUID]
    ) -> dict[UUID, Product]:
        products = {
            product.id: product
            for product in await self.repository.get_products(tenant_id, product_ids)
        }
        missing = product_ids - products.keys()
        if missing:
            raise AppError(
                status_code=404,
                code="PRODUCT_NOT_FOUND",
                message="A selected product was not found. Refresh products and try again.",
                field_errors={"items": "Select products from this business."},
            )
        archived = next((product for product in products.values() if product.archived), None)
        if archived:
            raise AppError(
                status_code=422,
                code="PRODUCT_ARCHIVED",
                message=f"Product has been archived: {archived.name}. Restore it before selling.",
                field_errors={"items": f"Product has been archived: {archived.name}."},
            )
        return products

    @staticmethod
    def _items_for_sale(sale_id: UUID, lines: list[CalculatedLine]) -> list[SaleItem]:
        return [
            SaleItem(
                id=uuid4(),
                sale_id=sale_id,
                product_id=line.product.id,
                line_number=line_number,
                quantity=line.request.quantity,
                unit_price=line.request.unit_price,
                line_total=line.line_total,
                product_name_snapshot=line.product.name,
                unit_snapshot=line.product.unit,
            )
            for line_number, line in enumerate(lines, start=1)
        ]

    async def _default_warehouse(self, tenant_id: UUID) -> Warehouse:
        warehouse = await self.inventory.get_default_warehouse(tenant_id)
        if warehouse is None or warehouse.archived:
            raise AppError(
                status_code=409,
                code="DEFAULT_WAREHOUSE_UNAVAILABLE",
                message="The default warehouse is unavailable. Restore it before posting sales.",
            )
        return warehouse

    @staticmethod
    def _sale_movement(
        *, sale: Sale, item: SaleItem, warehouse: Warehouse, user_id: UUID
    ) -> StockMovement:
        key = f"sale-post:{sale.id}:{item.id}"
        return StockMovement(
            id=uuid4(),
            tenant_id=sale.tenant_id,
            product_id=item.product_id,
            warehouse_id=warehouse.id,
            movement_type="SALE",
            quantity=-item.quantity,
            unit=item.unit_snapshot,
            reference_type="SALE",
            reference_id=sale.id,
            remarks=None,
            created_by=user_id,
            idempotency_key=key,
            request_hash=hashlib.sha256(key.encode()).hexdigest(),
        )

    @staticmethod
    def _void_movement(*, sale: Sale, original: StockMovement, user_id: UUID) -> StockMovement:
        key = f"sale-void:{sale.id}:{original.id}"
        return StockMovement(
            id=uuid4(),
            tenant_id=sale.tenant_id,
            product_id=original.product_id,
            warehouse_id=original.warehouse_id,
            movement_type="SALE_VOID",
            quantity=-original.quantity,
            unit=original.unit,
            reference_type="SALE",
            reference_id=sale.id,
            remarks=None,
            created_by=user_id,
            idempotency_key=key,
            request_hash=hashlib.sha256(key.encode()).hexdigest(),
        )

    @staticmethod
    def _require_sale(sale: Sale | None) -> Sale:
        if sale is None:
            raise AppError(
                status_code=404,
                code="SALE_NOT_FOUND",
                message="This sale was not found. Refresh the sales list and try again.",
            )
        return sale

    @staticmethod
    def _require_draft(sale: Sale) -> None:
        if sale.status != "DRAFT":
            raise AppError(
                status_code=409,
                code="SALE_NOT_EDITABLE",
                message=("Only draft sales can be edited. Posted and voided sales are read only."),
            )

    @staticmethod
    def _idempotency_key(value: str | None) -> str:
        if value is None or not value.strip():
            raise AppError(
                status_code=422,
                code="IDEMPOTENCY_KEY_REQUIRED",
                message="A submission key is required. Submit the sale again.",
                field_errors={"idempotency_key": "Submit again to generate a new key."},
            )
        key = value.strip()
        if len(key) > 128:
            raise AppError(
                status_code=422,
                code="IDEMPOTENCY_KEY_INVALID",
                message="The submission key is too long. Submit the sale again.",
                field_errors={"idempotency_key": "Submission key is too long."},
            )
        return key

    @staticmethod
    def _request_hash(request: SaleCreateRequest) -> str:
        items = sorted(
            (
                {
                    "product_id": str(item.product_id),
                    "quantity": str(item.quantity),
                    "unit_price": str(item.unit_price),
                }
                for item in request.items
            ),
            key=lambda item: item["product_id"],
        )
        raw = json.dumps(
            {"customer_id": str(request.customer_id), "items": items},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _idempotency_reused() -> AppError:
        return AppError(
            status_code=409,
            code="IDEMPOTENCY_KEY_REUSED",
            message=(
                "This submission key was already used for a different sale operation. "
                "Submit again to generate a new key."
            ),
            field_errors={"idempotency_key": "Use a new submission key and try again."},
        )

    @staticmethod
    def _fingerprint(
        *,
        sale_status: SaleStatusFilter,
        sale_sort: SaleSort,
        search: str | None,
        sale_date: date | None,
    ) -> str:
        raw = json.dumps(
            {
                "status": sale_status,
                "sort": sale_sort,
                "search": (search or "").strip().lower(),
                "date": sale_date.isoformat() if sale_date else "",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @classmethod
    def _encode_cursor(
        cls,
        *,
        created_at: datetime,
        sale_id: UUID,
        sale_status: SaleStatusFilter,
        sale_sort: SaleSort,
        search: str | None,
        sale_date: date | None,
    ) -> str:
        payload = {
            "v": 1,
            "created_at": created_at.isoformat(),
            "id": str(sale_id),
            "fingerprint": cls._fingerprint(
                sale_status=sale_status,
                sale_sort=sale_sort,
                search=search,
                sale_date=sale_date,
            ),
        }
        return (
            base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
            .decode()
            .rstrip("=")
        )

    @classmethod
    def _decode_cursor(
        cls,
        cursor: str | None,
        *,
        sale_status: SaleStatusFilter,
        sale_sort: SaleSort,
        search: str | None,
        sale_date: date | None,
    ) -> tuple[datetime | None, UUID | None]:
        if cursor is None:
            return None, None
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload = cast(dict[str, Any], json.loads(base64.urlsafe_b64decode(padded)))
            if payload.get("v") != 1 or payload.get("fingerprint") != cls._fingerprint(
                sale_status=sale_status,
                sale_sort=sale_sort,
                search=search,
                sale_date=sale_date,
            ):
                raise ValueError
            return datetime.fromisoformat(str(payload["created_at"])), UUID(str(payload["id"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AppError(
                status_code=422,
                code="INVALID_SALE_CURSOR",
                message="This sales page is no longer valid. Refresh the list and try again.",
                field_errors={"cursor": "Refresh the sales list before loading more."},
            ) from exc


def _date_range(value: date | None, timezone_name: str) -> tuple[datetime | None, datetime | None]:
    if value is None:
        return None, None
    timezone = ZoneInfo(timezone_name)
    start = datetime.combine(value, time.min, tzinfo=timezone).astimezone(UTC)
    return start, start + timedelta(days=1)


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _constraint_name(exc: IntegrityError) -> str | None:
    current: BaseException | None = exc.orig
    while current is not None:
        constraint = cast(str | None, getattr(current, "constraint_name", None))
        if constraint:
            return constraint
        current = current.__cause__
    return None
