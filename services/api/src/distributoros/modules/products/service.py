import base64
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from uuid import UUID, uuid4

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.errors import AppError
from distributoros.modules.products.models import Product
from distributoros.modules.products.repository import ProductPage, ProductRepository
from distributoros.modules.products.schemas import (
    ProductCreateRequest,
    ProductSort,
    ProductStatus,
    ProductUpdateRequest,
)


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProductRepository(session)
        self.logger = structlog.get_logger("distributoros.products")

    async def create(
        self, request: ProductCreateRequest, *, tenant_id: UUID, user_id: UUID
    ) -> Product:
        product = Product(
            id=uuid4(),
            tenant_id=tenant_id,
            product_code=await self.repository.next_product_code(tenant_id),
            created_by=user_id,
            updated_by=user_id,
            **request.model_dump(),
        )
        self.repository.add(product)
        await self._flush_with_unique_errors()
        self.logger.info(
            "product_created",
            tenant_id=str(tenant_id),
            product_id=str(product.id),
            product_code=product.product_code,
            user_id=str(user_id),
        )
        return product

    async def get(self, product_id: UUID, *, tenant_id: UUID) -> Product:
        return self._require_product(await self.repository.get(tenant_id, product_id))

    async def get_by_code(self, product_code: str, *, tenant_id: UUID) -> Product:
        return self._require_product(await self.repository.get_by_code(tenant_id, product_code))

    async def update(
        self,
        product_id: UUID,
        request: ProductUpdateRequest,
        *,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Product:
        product = await self.get(product_id, tenant_id=tenant_id)
        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        product.updated_by = user_id
        product.updated_at = datetime.now(UTC)
        await self._flush_with_unique_errors()
        self.logger.info(
            "product_updated",
            tenant_id=str(tenant_id),
            product_id=str(product.id),
            user_id=str(user_id),
        )
        return product

    async def set_archived(
        self,
        product_id: UUID,
        *,
        archived: bool,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Product:
        product = await self.get(product_id, tenant_id=tenant_id)
        if product.archived != archived:
            product.archived = archived
            product.updated_by = user_id
            product.updated_at = datetime.now(UTC)
            await self.session.flush()
        self.logger.info(
            "product_archived" if archived else "product_restored",
            tenant_id=str(tenant_id),
            product_id=str(product.id),
            user_id=str(user_id),
        )
        return product

    async def list(
        self,
        *,
        tenant_id: UUID,
        product_status: ProductStatus,
        product_sort: ProductSort,
        search: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[ProductPage, str | None]:
        cursor_key, cursor_id = self._decode_cursor(
            cursor,
            product_sort=product_sort,
            product_status=product_status,
            search=search,
        )
        page = await self.repository.list(
            tenant_id=tenant_id,
            product_status=product_status,
            product_sort=product_sort,
            search=search,
            limit=limit,
            cursor_key=cursor_key,
            cursor_id=cursor_id,
        )
        next_cursor = None
        if page.has_more and page.items:
            last = page.items[-1]
            if product_sort in {"newest", "oldest"}:
                key = last.created_at.isoformat()
            elif product_sort in {"price_asc", "price_desc"}:
                key = str(last.selling_price)
            else:
                key = last.name.lower()
            next_cursor = self._encode_cursor(
                key=key,
                product_id=last.id,
                product_sort=product_sort,
                product_status=product_status,
                search=search,
            )
        return page, next_cursor

    async def _flush_with_unique_errors(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            constraint = _unique_constraint(exc)
            errors = {
                "uq_products_tenant_name_ci": (
                    "PRODUCT_NAME_ALREADY_EXISTS",
                    "A product with this name already exists.",
                    "name",
                ),
                "uq_products_tenant_sku_ci": (
                    "PRODUCT_SKU_ALREADY_EXISTS",
                    "This SKU already exists.",
                    "sku",
                ),
                "uq_products_tenant_barcode": (
                    "PRODUCT_BARCODE_ALREADY_EXISTS",
                    "Barcode already exists.",
                    "barcode",
                ),
                "ck_products_inventory_unit_locked": (
                    "PRODUCT_UNIT_LOCKED",
                    (
                        "Unit cannot be changed after inventory has been recorded. "
                        "Create a new product if a different unit is required."
                    ),
                    "unit",
                ),
            }
            error = errors.get(constraint) if constraint else None
            if error:
                code, message, field = error
                raise AppError(
                    status_code=409,
                    code=code,
                    message=message,
                    field_errors={field: message},
                ) from exc
            raise

    @staticmethod
    def _require_product(product: Product | None) -> Product:
        if product is None:
            raise AppError(
                status_code=404,
                code="PRODUCT_NOT_FOUND",
                message="This product was not found. Refresh the product list and try again.",
            )
        return product

    @staticmethod
    def _fingerprint(
        *, product_sort: ProductSort, product_status: ProductStatus, search: str | None
    ) -> str:
        value = json.dumps(
            {
                "sort": product_sort,
                "status": product_status,
                "search": (search or "").strip().lower(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(value.encode()).hexdigest()[:16]

    @classmethod
    def _encode_cursor(
        cls,
        *,
        key: str,
        product_id: UUID,
        product_sort: ProductSort,
        product_status: ProductStatus,
        search: str | None,
    ) -> str:
        payload = {
            "v": 1,
            "key": key,
            "id": str(product_id),
            "fingerprint": cls._fingerprint(
                product_sort=product_sort,
                product_status=product_status,
                search=search,
            ),
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def _decode_cursor(
        cls,
        cursor: str | None,
        *,
        product_sort: ProductSort,
        product_status: ProductStatus,
        search: str | None,
    ) -> tuple[str | datetime | Decimal | None, UUID | None]:
        if cursor is None:
            return None, None
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload: dict[str, Any] = json.loads(base64.urlsafe_b64decode(padded))
            if payload.get("v") != 1 or payload.get("fingerprint") != cls._fingerprint(
                product_sort=product_sort,
                product_status=product_status,
                search=search,
            ):
                raise ValueError
            product_id = UUID(str(payload["id"]))
            raw_key = str(payload["key"])
            key: str | datetime | Decimal
            if product_sort in {"newest", "oldest"}:
                key = datetime.fromisoformat(raw_key)
            elif product_sort in {"price_asc", "price_desc"}:
                key = Decimal(raw_key)
            else:
                key = raw_key
            return key, product_id
        except (
            KeyError,
            TypeError,
            ValueError,
            InvalidOperation,
            json.JSONDecodeError,
        ) as exc:
            raise AppError(
                status_code=422,
                code="INVALID_PRODUCT_CURSOR",
                message=(
                    "This product list page is no longer valid. Refresh the list and try again."
                ),
                field_errors={"cursor": "Refresh the product list before loading more."},
            ) from exc


def _unique_constraint(exc: IntegrityError) -> str | None:
    current: BaseException | None = exc.orig
    while current is not None:
        constraint = cast(str | None, getattr(current, "constraint_name", None))
        if getattr(current, "sqlstate", None) in {"23505", "23514"} and constraint:
            return constraint
        current = current.__cause__
    return None
