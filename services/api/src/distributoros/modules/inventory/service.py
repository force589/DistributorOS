import base64
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.errors import AppError
from distributoros.modules.inventory.models import StockMovement, Warehouse
from distributoros.modules.inventory.repository import (
    InventoryRepository,
    MovementRow,
    Page,
    StockRow,
)
from distributoros.modules.inventory.schemas import (
    AdjustmentRequest,
    LowStockStatus,
    MovementType,
    PositiveStockRequest,
)
from distributoros.modules.products.models import Product


class InventoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = InventoryRepository(session)
        self.logger = structlog.get_logger("distributoros.inventory")

    async def default_warehouse(self, tenant_id: UUID) -> Warehouse:
        warehouse = await self.repository.get_default_warehouse(tenant_id)
        if warehouse is None:
            raise AppError(
                status_code=409,
                code="DEFAULT_WAREHOUSE_MISSING",
                message=(
                    "This business does not have a default warehouse. "
                    "Contact support before recording inventory."
                ),
            )
        return warehouse

    async def post_positive(
        self,
        request: PositiveStockRequest,
        *,
        movement_type: MovementType,
        idempotency_key: str | None,
        tenant_id: UUID,
        user_id: UUID,
    ) -> tuple[MovementRow, StockRow]:
        delta = -request.quantity if movement_type in {"DAMAGED", "SPOILAGE"} else request.quantity
        return await self._post(
            product_id=request.product_id,
            warehouse_id=request.warehouse_id,
            movement_type=movement_type,
            delta=delta,
            remarks=request.remarks,
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    async def post_adjustment(
        self,
        request: AdjustmentRequest,
        *,
        idempotency_key: str | None,
        tenant_id: UUID,
        user_id: UUID,
    ) -> tuple[MovementRow, StockRow]:
        return await self._post(
            product_id=request.product_id,
            warehouse_id=request.warehouse_id,
            movement_type="STOCK_ADJUSTMENT",
            delta=request.quantity,
            remarks=request.reason,
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    async def _post(
        self,
        *,
        product_id: UUID,
        warehouse_id: UUID | None,
        movement_type: MovementType,
        delta: Decimal,
        remarks: str | None,
        idempotency_key: str | None,
        tenant_id: UUID,
        user_id: UUID,
    ) -> tuple[MovementRow, StockRow]:
        key = self._validate_idempotency_key(idempotency_key)
        product = await self._require_product(tenant_id, product_id)
        warehouse = await self._require_warehouse(tenant_id, warehouse_id)
        request_hash = self._request_hash(
            movement_type=movement_type,
            product_id=product.id,
            warehouse_id=warehouse.id,
            delta=delta,
            remarks=remarks,
        )
        movement = StockMovement(
            id=uuid4(),
            tenant_id=tenant_id,
            product_id=product.id,
            warehouse_id=warehouse.id,
            movement_type=movement_type,
            quantity=delta,
            unit=product.unit,
            reference_type=None,
            reference_id=None,
            remarks=remarks,
            created_by=user_id,
            idempotency_key=key,
            request_hash=request_hash,
        )
        try:
            async with self.session.begin_nested():
                self.repository.add_movement(movement)
                await self.session.flush()
        except IntegrityError as exc:
            constraint = _constraint_name(exc)
            if constraint == "uq_stock_movements_tenant_idempotency":
                existing = await self.repository.get_movement_by_idempotency(tenant_id, key)
                if existing is None:
                    raise
                if existing.request_hash != request_hash:
                    raise AppError(
                        status_code=409,
                        code="IDEMPOTENCY_KEY_REUSED",
                        message=(
                            "This submission key was already used for a different inventory "
                            "operation. Submit again to create a new operation."
                        ),
                        field_errors={"idempotency_key": "Use a new submission key and try again."},
                    ) from exc
                return await self._load_posted(tenant_id, existing, product, warehouse)
            if constraint == "uq_stock_movements_opening_stock":
                raise AppError(
                    status_code=409,
                    code="OPENING_STOCK_ALREADY_RECORDED",
                    message=(
                        "Opening stock has already been recorded for this product. "
                        "Use a stock adjustment to correct it."
                    ),
                    field_errors={
                        "quantity": ("Opening stock already exists. Record an adjustment instead.")
                    },
                ) from exc
            raise

        try:
            balance = await self.repository.apply_delta(
                tenant_id=tenant_id,
                product_id=product.id,
                warehouse_id=warehouse.id,
                delta=delta,
            )
        except IntegrityError as exc:
            if _constraint_name(exc) == "ck_stock_balances_quantity_not_negative":
                raise self._insufficient_stock() from exc
            raise
        if balance is None:
            raise self._insufficient_stock()
        await self.session.flush()
        movement_row = await self.repository.movement_row(tenant_id, movement.id)
        stock = StockRow(
            product=product,
            warehouse=warehouse,
            available_quantity=balance[0],
            updated_at=balance[1],
        )
        if movement_row is None:
            raise RuntimeError("Posted inventory operation could not be reloaded.")
        self.logger.info(
            "stock_movement_posted",
            tenant_id=str(tenant_id),
            movement_id=str(movement.id),
            movement_type=movement_type,
            product_id=str(product.id),
            warehouse_id=str(warehouse.id),
            user_id=str(user_id),
        )
        return movement_row, stock

    async def _load_posted(
        self,
        tenant_id: UUID,
        movement: StockMovement,
        product: Product,
        warehouse: Warehouse,
    ) -> tuple[MovementRow, StockRow]:
        movement_row = await self.repository.movement_row(tenant_id, movement.id)
        stock = await self.repository.get_stock(
            tenant_id=tenant_id,
            product_id=product.id,
            warehouse_id=warehouse.id,
        )
        if movement_row is None or stock is None:
            raise RuntimeError("Idempotent inventory operation could not be reloaded.")
        return movement_row, stock

    async def get_current_stock(
        self, *, tenant_id: UUID, product_id: UUID, warehouse_id: UUID | None
    ) -> StockRow:
        product = await self.repository.get_product(tenant_id, product_id)
        if product is None:
            raise self._product_not_found()
        warehouse = await self._require_warehouse(tenant_id, warehouse_id)
        stock = await self.repository.get_stock(
            tenant_id=tenant_id,
            product_id=product.id,
            warehouse_id=warehouse.id,
        )
        if stock is None:
            raise self._product_not_found()
        return stock

    async def list_stock(
        self,
        *,
        tenant_id: UUID,
        warehouse_id: UUID | None,
        search: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[Page[StockRow], str | None]:
        warehouse = await self._require_warehouse(tenant_id, warehouse_id)
        cursor_name, cursor_id = self._decode_stock_cursor(cursor, search=search)
        page = await self.repository.list_stock(
            tenant_id=tenant_id,
            warehouse_id=warehouse.id,
            search=search,
            limit=limit,
            cursor_name=cursor_name,
            cursor_id=cursor_id,
        )
        next_cursor = None
        if page.has_more and page.items:
            last = page.items[-1].product
            next_cursor = self._encode_cursor(
                {"v": 1, "name": last.name.lower(), "id": str(last.id)},
                fingerprint=self._fingerprint({"search": (search or "").strip().lower()}),
            )
        return page, next_cursor

    async def list_history(
        self,
        *,
        tenant_id: UUID,
        warehouse_id: UUID | None,
        product_id: UUID | None,
        search: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[Page[MovementRow], str | None]:
        warehouse = await self._require_warehouse(tenant_id, warehouse_id)
        if product_id and await self.repository.get_product(tenant_id, product_id) is None:
            raise self._product_not_found()
        cursor_created, cursor_id = self._decode_history_cursor(
            cursor, product_id=product_id, search=search
        )
        page = await self.repository.list_history(
            tenant_id=tenant_id,
            warehouse_id=warehouse.id,
            product_id=product_id,
            search=search,
            limit=limit,
            cursor_created_at=cursor_created,
            cursor_id=cursor_id,
        )
        next_cursor = None
        if page.has_more and page.items:
            last = page.items[-1].movement
            next_cursor = self._encode_cursor(
                {"v": 1, "created": last.created_at.isoformat(), "id": str(last.id)},
                fingerprint=self._fingerprint(
                    {
                        "product_id": str(product_id or ""),
                        "search": (search or "").strip().lower(),
                    }
                ),
            )
        return page, next_cursor

    async def _require_product(self, tenant_id: UUID, product_id: UUID) -> Product:
        product = await self.repository.get_product(tenant_id, product_id)
        if product is None:
            raise self._product_not_found()
        if product.archived:
            raise AppError(
                status_code=422,
                code="PRODUCT_ARCHIVED",
                message="Selected product has been archived. Restore it before adding stock.",
                field_errors={"product_id": "Selected product has been archived."},
            )
        return product

    async def _require_warehouse(self, tenant_id: UUID, warehouse_id: UUID | None) -> Warehouse:
        warehouse = (
            await self.repository.get_warehouse(tenant_id, warehouse_id)
            if warehouse_id
            else await self.repository.get_default_warehouse(tenant_id)
        )
        if warehouse is None:
            raise AppError(
                status_code=404,
                code="WAREHOUSE_NOT_FOUND",
                message="This warehouse was not found. Refresh and try again.",
                field_errors={"warehouse_id": "Select a warehouse from this business."},
            )
        if warehouse.archived:
            raise AppError(
                status_code=422,
                code="WAREHOUSE_ARCHIVED",
                message="This warehouse is archived. Select an active warehouse.",
                field_errors={"warehouse_id": "This warehouse is archived."},
            )
        return warehouse

    @staticmethod
    def low_stock_status(quantity: Decimal, threshold: Decimal) -> LowStockStatus:
        if quantity == 0:
            return "OUT_OF_STOCK"
        if quantity <= threshold:
            return "LOW_STOCK"
        return "NORMAL"

    @staticmethod
    def _validate_idempotency_key(value: str | None) -> str:
        if value is None or not value.strip():
            raise AppError(
                status_code=422,
                code="IDEMPOTENCY_KEY_REQUIRED",
                message="A submission key is required. Submit the inventory operation again.",
                field_errors={"idempotency_key": "Submit again to generate a new submission key."},
            )
        normalized = value.strip()
        if len(normalized) > 128:
            raise AppError(
                status_code=422,
                code="IDEMPOTENCY_KEY_INVALID",
                message="The submission key is too long. Submit the operation again.",
                field_errors={"idempotency_key": "Submission key must not exceed 128 characters."},
            )
        return normalized

    @staticmethod
    def _request_hash(
        *,
        movement_type: MovementType,
        product_id: UUID,
        warehouse_id: UUID,
        delta: Decimal,
        remarks: str | None,
    ) -> str:
        value = json.dumps(
            {
                "movement_type": movement_type,
                "product_id": str(product_id),
                "warehouse_id": str(warehouse_id),
                "quantity": str(delta),
                "remarks": remarks,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(value.encode()).hexdigest()

    @staticmethod
    def _fingerprint(value: dict[str, str]) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @classmethod
    def _encode_cursor(cls, payload: dict[str, Any], *, fingerprint: str) -> str:
        payload["fingerprint"] = fingerprint
        return (
            base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
            .decode()
            .rstrip("=")
        )

    @classmethod
    def _decode_stock_cursor(
        cls, cursor: str | None, *, search: str | None
    ) -> tuple[str | None, UUID | None]:
        if cursor is None:
            return None, None
        payload = cls._decode_cursor(
            cursor,
            fingerprint=cls._fingerprint({"search": (search or "").strip().lower()}),
        )
        try:
            return str(payload["name"]), UUID(str(payload["id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise cls._invalid_cursor() from exc

    @classmethod
    def _decode_history_cursor(
        cls,
        cursor: str | None,
        *,
        product_id: UUID | None,
        search: str | None,
    ) -> tuple[datetime | None, UUID | None]:
        if cursor is None:
            return None, None
        payload = cls._decode_cursor(
            cursor,
            fingerprint=cls._fingerprint(
                {
                    "product_id": str(product_id or ""),
                    "search": (search or "").strip().lower(),
                }
            ),
        )
        try:
            return datetime.fromisoformat(str(payload["created"])), UUID(str(payload["id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise cls._invalid_cursor() from exc

    @classmethod
    def _decode_cursor(cls, cursor: str, *, fingerprint: str) -> dict[str, Any]:
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload = cast(dict[str, Any], json.loads(base64.urlsafe_b64decode(padded)))
            if payload.get("v") != 1 or payload.get("fingerprint") != fingerprint:
                raise ValueError
            return payload
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise cls._invalid_cursor() from exc

    @staticmethod
    def _invalid_cursor() -> AppError:
        return AppError(
            status_code=422,
            code="INVALID_INVENTORY_CURSOR",
            message="This inventory page is no longer valid. Refresh the list and try again.",
            field_errors={"cursor": "Refresh the inventory list before loading more."},
        )

    @staticmethod
    def _product_not_found() -> AppError:
        return AppError(
            status_code=404,
            code="PRODUCT_NOT_FOUND",
            message="This product was not found. Refresh the product list and try again.",
            field_errors={"product_id": "Select a product from this business."},
        )

    @staticmethod
    def _insufficient_stock() -> AppError:
        return AppError(
            status_code=409,
            code="INSUFFICIENT_STOCK",
            message="This operation would reduce stock below zero. Enter a smaller quantity.",
            field_errors={"quantity": "Only the available stock can be removed."},
        )


def _constraint_name(exc: IntegrityError) -> str | None:
    current: BaseException | None = exc.orig
    while current is not None:
        constraint = cast(str | None, getattr(current, "constraint_name", None))
        if constraint:
            return constraint
        current = current.__cause__
    return None
