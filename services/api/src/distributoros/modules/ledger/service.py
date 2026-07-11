from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from distributoros.core.errors import AppError
from distributoros.modules.ledger.models import (
    CustomerBalanceProjection,
    CustomerLedgerEntry,
)
from distributoros.modules.ledger.repository import LedgerPage, LedgerRepository
from distributoros.modules.ledger.schemas import LedgerEntryTypeFilter
from distributoros.modules.payments.models import Payment
from distributoros.modules.sales.models import Sale
from distributoros.modules.tenancy.models import Business


class FinancialPostingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = LedgerRepository(session)
        self.logger = structlog.get_logger("distributoros.ledger.posting")

    async def post_sale(self, sale: Sale, *, user_id: UUID) -> None:
        entries = await self.repository.entries_for_sale(sale.tenant_id, sale.id)
        if entries:
            raise self._corrupt_state()
        projection = await self.repository.get_projection(
            sale.tenant_id, sale.customer_id, for_update=True
        )
        has_history = await self.repository.has_customer_entries(sale.tenant_id, sale.customer_id)
        if (projection is None and has_history) or (projection is not None and not has_history):
            raise self._corrupt_state()
        posted_at = datetime.now(UTC)
        self.repository.add_entry(
            CustomerLedgerEntry(
                id=uuid4(),
                tenant_id=sale.tenant_id,
                customer_id=sale.customer_id,
                entry_type="SALE",
                reference_type="SALE",
                reference_id=sale.id,
                debit=sale.subtotal,
                credit=Decimal("0.00"),
                remarks=None,
                created_at=posted_at,
                created_by=user_id,
            )
        )
        await self.session.flush()
        await self.repository.apply_sale_projection(
            tenant_id=sale.tenant_id,
            customer_id=sale.customer_id,
            amount=sale.subtotal,
            sale_at=posted_at,
        )
        self.logger.info(
            "sale_financially_posted",
            tenant_id=str(sale.tenant_id),
            sale_id=str(sale.id),
            customer_id=str(sale.customer_id),
            amount=str(sale.subtotal),
        )

    async def validate_posted_sale(self, sale: Sale) -> None:
        entries = await self.repository.entries_for_sale(sale.tenant_id, sale.id)
        if not self._valid_posted_entries(sale, entries):
            raise self._corrupt_state()
        if await self.repository.get_projection(sale.tenant_id, sale.customer_id) is None:
            raise self._corrupt_state()

    async def validate_can_void(self, sale: Sale) -> None:
        entries = await self.repository.entries_for_sale(sale.tenant_id, sale.id)
        if not self._valid_posted_entries(sale, entries):
            raise self._corrupt_state()

    async def void_sale(self, sale: Sale, *, user_id: UUID) -> None:
        entries = await self.repository.entries_for_sale(sale.tenant_id, sale.id)
        if not self._valid_posted_entries(sale, entries):
            raise self._corrupt_state()
        projection = await self.repository.get_projection(
            sale.tenant_id, sale.customer_id, for_update=True
        )
        if projection is None:
            raise self._corrupt_state()
        self.repository.add_entry(
            CustomerLedgerEntry(
                id=uuid4(),
                tenant_id=sale.tenant_id,
                customer_id=sale.customer_id,
                entry_type="REVERSAL",
                reference_type="SALE",
                reference_id=sale.id,
                debit=Decimal("0.00"),
                credit=sale.subtotal,
                remarks=None,
                created_by=user_id,
            )
        )
        await self.session.flush()
        updated = await self.repository.apply_reversal_projection(
            tenant_id=sale.tenant_id,
            customer_id=sale.customer_id,
            amount=sale.subtotal,
        )
        if not updated:
            raise self._corrupt_state()
        self.logger.info(
            "sale_financial_posting_reversed",
            tenant_id=str(sale.tenant_id),
            sale_id=str(sale.id),
            customer_id=str(sale.customer_id),
            amount=str(sale.subtotal),
        )

    async def validate_voided_sale(self, sale: Sale) -> None:
        entries = await self.repository.entries_for_sale(sale.tenant_id, sale.id)
        if not self._valid_voided_entries(sale, entries):
            raise self._corrupt_state()
        if await self.repository.get_projection(sale.tenant_id, sale.customer_id) is None:
            raise self._corrupt_state()

    async def post_payment(self, payment: Payment, *, user_id: UUID) -> None:
        entries = await self.repository.entries_for_payment(payment.tenant_id, payment.id)
        if entries:
            raise self._corrupt_state()
        projection = await self.repository.get_projection(
            payment.tenant_id, payment.customer_id, for_update=True
        )
        has_history = await self.repository.has_customer_entries(
            payment.tenant_id, payment.customer_id
        )
        if (projection is None and has_history) or (projection is not None and not has_history):
            raise self._corrupt_state()
        posted_at = datetime.now(UTC)
        self.repository.add_entry(
            CustomerLedgerEntry(
                id=uuid4(),
                tenant_id=payment.tenant_id,
                customer_id=payment.customer_id,
                entry_type="PAYMENT",
                reference_type="PAYMENT",
                reference_id=payment.id,
                debit=Decimal("0.00"),
                credit=payment.amount,
                remarks=None,
                created_at=posted_at,
                created_by=user_id,
            )
        )
        await self.session.flush()
        updated = await self.repository.apply_payment_projection(
            tenant_id=payment.tenant_id,
            customer_id=payment.customer_id,
            amount=payment.amount,
            payment_at=posted_at,
        )
        if not updated:
            raise self._corrupt_state()
        self.logger.info(
            "payment_financially_posted",
            tenant_id=str(payment.tenant_id),
            payment_id=str(payment.id),
            customer_id=str(payment.customer_id),
            amount=str(payment.amount),
        )

    async def validate_posted_payment(self, payment: Payment) -> None:
        entries = await self.repository.entries_for_payment(payment.tenant_id, payment.id)
        if not self._valid_posted_payment_entries(payment, entries):
            raise self._corrupt_state()
        if await self.repository.get_projection(payment.tenant_id, payment.customer_id) is None:
            raise self._corrupt_state()

    async def validate_can_void_payment(self, payment: Payment) -> None:
        entries = await self.repository.entries_for_payment(payment.tenant_id, payment.id)
        if not self._valid_posted_payment_entries(payment, entries):
            raise self._corrupt_state()

    async def void_payment(self, payment: Payment, *, user_id: UUID) -> None:
        entries = await self.repository.entries_for_payment(payment.tenant_id, payment.id)
        if not self._valid_posted_payment_entries(payment, entries):
            raise self._corrupt_state()
        projection = await self.repository.get_projection(
            payment.tenant_id, payment.customer_id, for_update=True
        )
        if projection is None:
            raise self._corrupt_state()
        self.repository.add_entry(
            CustomerLedgerEntry(
                id=uuid4(),
                tenant_id=payment.tenant_id,
                customer_id=payment.customer_id,
                entry_type="PAYMENT_REVERSAL",
                reference_type="PAYMENT",
                reference_id=payment.id,
                debit=payment.amount,
                credit=Decimal("0.00"),
                remarks=None,
                created_by=user_id,
            )
        )
        await self.session.flush()
        updated = await self.repository.apply_payment_reversal_projection(
            tenant_id=payment.tenant_id,
            customer_id=payment.customer_id,
            amount=payment.amount,
        )
        if not updated:
            raise self._corrupt_state()
        self.logger.info(
            "payment_financial_posting_reversed",
            tenant_id=str(payment.tenant_id),
            payment_id=str(payment.id),
            customer_id=str(payment.customer_id),
            amount=str(payment.amount),
        )

    async def validate_voided_payment(self, payment: Payment) -> None:
        entries = await self.repository.entries_for_payment(payment.tenant_id, payment.id)
        if not self._valid_voided_payment_entries(payment, entries):
            raise self._corrupt_state()
        if await self.repository.get_projection(payment.tenant_id, payment.customer_id) is None:
            raise self._corrupt_state()

    @staticmethod
    def _valid_posted_entries(sale: Sale, entries: list[CustomerLedgerEntry]) -> bool:
        return (
            len(entries) == 1
            and entries[0].entry_type == "SALE"
            and entries[0].customer_id == sale.customer_id
            and entries[0].debit == sale.subtotal
            and entries[0].credit == Decimal("0.00")
        )

    @staticmethod
    def _valid_voided_entries(sale: Sale, entries: list[CustomerLedgerEntry]) -> bool:
        reversals = [entry for entry in entries if entry.entry_type == "REVERSAL"]
        return (
            len(entries) == 2
            and FinancialPostingService._valid_posted_entries(
                sale, [entry for entry in entries if entry.entry_type == "SALE"]
            )
            and len(reversals) == 1
            and reversals[0].customer_id == sale.customer_id
            and reversals[0].debit == Decimal("0.00")
            and reversals[0].credit == sale.subtotal
        )

    @staticmethod
    def _valid_posted_payment_entries(payment: Payment, entries: list[CustomerLedgerEntry]) -> bool:
        return (
            len(entries) == 1
            and entries[0].entry_type == "PAYMENT"
            and entries[0].customer_id == payment.customer_id
            and entries[0].debit == Decimal("0.00")
            and entries[0].credit == payment.amount
        )

    @staticmethod
    def _valid_voided_payment_entries(payment: Payment, entries: list[CustomerLedgerEntry]) -> bool:
        reversals = [entry for entry in entries if entry.entry_type == "PAYMENT_REVERSAL"]
        return (
            len(entries) == 2
            and FinancialPostingService._valid_posted_payment_entries(
                payment, [entry for entry in entries if entry.entry_type == "PAYMENT"]
            )
            and len(reversals) == 1
            and reversals[0].customer_id == payment.customer_id
            and reversals[0].debit == payment.amount
            and reversals[0].credit == Decimal("0.00")
        )

    @staticmethod
    def _corrupt_state() -> AppError:
        return AppError(
            status_code=409,
            code="LEDGER_STATE_CORRUPT",
            message=(
                "The customer ledger is inconsistent for this financial event. "
                "Run ledger reconciliation before trying again."
            ),
        )


class LedgerQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = LedgerRepository(session)

    async def summary(
        self, *, tenant_id: UUID, customer_id: UUID
    ) -> CustomerBalanceProjection | None:
        await self._require_customer(tenant_id, customer_id)
        projection = await self.repository.get_projection(tenant_id, customer_id)
        if projection is None and await self.repository.has_customer_entries(
            tenant_id, customer_id
        ):
            raise FinancialPostingService._corrupt_state()
        return projection

    async def list_entries(
        self,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        entry_type: LedgerEntryTypeFilter,
        reference: str | None,
        ledger_date: date | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[LedgerPage, str | None]:
        await self._require_customer(tenant_id, customer_id)
        timezone = await self.session.scalar(
            select(Business.timezone).where(Business.id == tenant_id)
        )
        date_from, date_to = _date_range(ledger_date, str(timezone or "Asia/Kolkata"))
        cursor_created_at, cursor_id = self._decode_cursor(
            cursor,
            customer_id=customer_id,
            entry_type=entry_type,
            reference=reference,
            ledger_date=ledger_date,
        )
        page = await self.repository.list_entries(
            tenant_id=tenant_id,
            customer_id=customer_id,
            entry_type=entry_type,
            reference=reference,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
        )
        next_cursor = None
        if page.has_more and page.items:
            last = page.items[-1]
            next_cursor = self._encode_cursor(
                created_at=last.created_at,
                entry_id=last.id,
                customer_id=customer_id,
                entry_type=entry_type,
                reference=reference,
                ledger_date=ledger_date,
            )
        return page, next_cursor

    async def _require_customer(self, tenant_id: UUID, customer_id: UUID) -> None:
        if await self.repository.get_customer(tenant_id, customer_id) is None:
            raise AppError(
                status_code=404,
                code="CUSTOMER_NOT_FOUND",
                message="This customer was not found. Refresh customers and try again.",
            )

    @staticmethod
    def _fingerprint(
        *,
        customer_id: UUID,
        entry_type: LedgerEntryTypeFilter,
        reference: str | None,
        ledger_date: date | None,
    ) -> str:
        raw = json.dumps(
            {
                "customer_id": str(customer_id),
                "entry_type": entry_type,
                "reference": (reference or "").strip().lower(),
                "date": ledger_date.isoformat() if ledger_date else "",
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
        entry_id: UUID,
        customer_id: UUID,
        entry_type: LedgerEntryTypeFilter,
        reference: str | None,
        ledger_date: date | None,
    ) -> str:
        payload = {
            "v": 1,
            "created_at": created_at.isoformat(),
            "id": str(entry_id),
            "fingerprint": cls._fingerprint(
                customer_id=customer_id,
                entry_type=entry_type,
                reference=reference,
                ledger_date=ledger_date,
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
        customer_id: UUID,
        entry_type: LedgerEntryTypeFilter,
        reference: str | None,
        ledger_date: date | None,
    ) -> tuple[datetime | None, UUID | None]:
        if cursor is None:
            return None, None
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload = cast(dict[str, Any], json.loads(base64.urlsafe_b64decode(padded)))
            if payload.get("v") != 1 or payload.get("fingerprint") != cls._fingerprint(
                customer_id=customer_id,
                entry_type=entry_type,
                reference=reference,
                ledger_date=ledger_date,
            ):
                raise ValueError
            return datetime.fromisoformat(str(payload["created_at"])), UUID(str(payload["id"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AppError(
                status_code=422,
                code="INVALID_LEDGER_CURSOR",
                message="This ledger page is no longer valid. Refresh the ledger and try again.",
                field_errors={"cursor": "Refresh the customer ledger before loading more."},
            ) from exc


def _date_range(value: date | None, timezone_name: str) -> tuple[datetime | None, datetime | None]:
    if value is None:
        return None, None
    timezone = ZoneInfo(timezone_name)
    start = datetime.combine(value, time.min, tzinfo=timezone).astimezone(UTC)
    return start, start + timedelta(days=1)
