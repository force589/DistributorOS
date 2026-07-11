from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import Select, func, or_, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.modules.products.models import Product
from distributoros.modules.products.schemas import ProductSort, ProductStatus


@dataclass(frozen=True)
class ProductPage:
    items: list[Product]
    has_more: bool


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def next_product_code(self, tenant_id: UUID) -> str:
        number = await self.session.scalar(
            text(
                """
                INSERT INTO product_code_counters (tenant_id, next_number)
                VALUES (:tenant_id, 2)
                ON CONFLICT (tenant_id) DO UPDATE
                SET next_number = product_code_counters.next_number + 1
                RETURNING next_number - 1
                """
            ),
            {"tenant_id": tenant_id},
        )
        if number is None:
            raise RuntimeError("Product code allocation did not return a number.")
        return f"PROD-{int(number):06d}"

    def add(self, product: Product) -> None:
        self.session.add(product)

    async def get(self, tenant_id: UUID, product_id: UUID) -> Product | None:
        statement = select(Product).where(
            Product.tenant_id == tenant_id,
            Product.id == product_id,
        )
        return cast(Product | None, await self.session.scalar(statement))

    async def get_by_code(self, tenant_id: UUID, product_code: str) -> Product | None:
        statement = select(Product).where(
            Product.tenant_id == tenant_id,
            Product.product_code == product_code.upper(),
        )
        return cast(Product | None, await self.session.scalar(statement))

    async def list(
        self,
        *,
        tenant_id: UUID,
        product_status: ProductStatus,
        product_sort: ProductSort,
        search: str | None,
        limit: int,
        cursor_key: str | datetime | Decimal | None,
        cursor_id: UUID | None,
    ) -> ProductPage:
        statement = select(Product).where(Product.tenant_id == tenant_id)
        if product_status == "active":
            statement = statement.where(Product.archived.is_(False))
        elif product_status == "archived":
            statement = statement.where(Product.archived.is_(True))

        if search:
            term = search.strip()
            lowered = term.lower()
            statement = statement.where(
                or_(
                    func.lower(Product.name).contains(lowered, autoescape=True),
                    func.lower(Product.product_code).contains(lowered, autoescape=True),
                    func.lower(Product.sku).contains(lowered, autoescape=True),
                    Product.barcode.contains(term, autoescape=True),
                    func.lower(Product.category).contains(lowered, autoescape=True),
                )
            )

        statement = self._apply_cursor_and_order(
            statement,
            product_sort=product_sort,
            cursor_key=cursor_key,
            cursor_id=cursor_id,
        ).limit(limit + 1)
        products = list((await self.session.scalars(statement)).all())
        return ProductPage(items=products[:limit], has_more=len(products) > limit)

    @staticmethod
    def _apply_cursor_and_order(
        statement: Select[tuple[Product]],
        *,
        product_sort: ProductSort,
        cursor_key: str | datetime | Decimal | None,
        cursor_id: UUID | None,
    ) -> Select[tuple[Product]]:
        if product_sort in {"newest", "oldest"}:
            if cursor_key is not None and cursor_id is not None:
                comparison = tuple_(Product.created_at, Product.id)
                statement = statement.where(
                    comparison < (cursor_key, cursor_id)
                    if product_sort == "newest"
                    else comparison > (cursor_key, cursor_id)
                )
            if product_sort == "newest":
                return statement.order_by(Product.created_at.desc(), Product.id.desc())
            return statement.order_by(Product.created_at.asc(), Product.id.asc())

        if product_sort in {"price_asc", "price_desc"}:
            if cursor_key is not None and cursor_id is not None:
                comparison = tuple_(Product.selling_price, Product.id)
                statement = statement.where(
                    comparison > (cursor_key, cursor_id)
                    if product_sort == "price_asc"
                    else comparison < (cursor_key, cursor_id)
                )
            if product_sort == "price_asc":
                return statement.order_by(Product.selling_price.asc(), Product.id.asc())
            return statement.order_by(Product.selling_price.desc(), Product.id.desc())

        normalized_name = func.lower(Product.name)
        if cursor_key is not None and cursor_id is not None:
            comparison = tuple_(normalized_name, Product.id)
            statement = statement.where(
                comparison > (cursor_key, cursor_id)
                if product_sort == "name_asc"
                else comparison < (cursor_key, cursor_id)
            )
        if product_sort == "name_asc":
            return statement.order_by(normalized_name.asc(), Product.id.asc())
        return statement.order_by(normalized_name.desc(), Product.id.desc())
