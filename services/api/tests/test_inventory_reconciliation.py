import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from distributoros.core.config import Settings
from distributoros.core.database import set_internal_maintenance_context
from distributoros.modules.inventory.reconcile_cli import _run
from distributoros.modules.inventory.reconciliation import (
    InventoryReconciliationService,
    RebuildBlockedError,
)


@pytest_asyncio.fixture
async def admin_engine(test_settings: Settings) -> AsyncIterator[AsyncEngine]:
    assert test_settings.database_admin_url is not None
    engine = create_async_engine(test_settings.database_admin_url)
    yield engine
    await engine.dispose()


@pytest.fixture
def reconciler(admin_engine: AsyncEngine) -> InventoryReconciliationService:
    return InventoryReconciliationService(admin_engine)


async def _signup(
    client: AsyncClient, suffix: str
) -> tuple[dict[str, Any], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "business_name": f"Reconciliation {suffix}",
            "email": f"reconcile-{suffix}@example.com",
            "password": "secure-pass-123",
        },
    )
    assert response.status_code == 201, response.text
    session: dict[str, Any] = response.json()
    return session, {"Authorization": f"Bearer {session['access_token']}"}


async def _product(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    *,
    unit: str = "piece",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": name,
            "selling_price": "10",
            "unit": unit,
            "low_stock_threshold": "2",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["product"]


async def _warehouse(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.get("/api/v1/inventory/warehouses/default", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _post(
    client: AsyncClient,
    headers: dict[str, str],
    path: str,
    product_id: str,
    quantity: str,
    *,
    warehouse_id: str | None = None,
    key: str | None = None,
    **fields: str,
) -> dict[str, Any]:
    payload = {"product_id": product_id, "quantity": quantity, **fields}
    if warehouse_id:
        payload["warehouse_id"] = warehouse_id
    response = await client.post(
        f"/api/v1/inventory/{path}",
        headers={**headers, "Idempotency-Key": key or str(uuid4())},
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _add_warehouse(
    engine: AsyncEngine, tenant_id: str, name: str
) -> UUID:
    warehouse_id = uuid4()
    async with engine.begin() as connection:
        await set_internal_maintenance_context(connection)
        await connection.execute(
            text(
                """
                INSERT INTO warehouses (
                    id, tenant_id, name, is_default, archived, created_at
                ) VALUES (
                    :id, :tenant_id, :name, false, false, now()
                )
                """
            ),
            {"id": warehouse_id, "tenant_id": tenant_id, "name": name},
        )
    return warehouse_id


async def test_empty_inventory_is_consistent(
    reconciler: InventoryReconciliationService,
) -> None:
    report = await reconciler.reconcile()
    assert report.is_consistent is True
    assert report.movement_count == 0
    assert report.rebuilt_balance_count == 0
    assert report.projection_count == 0
    assert report.discrepancy_count == 0


async def test_one_opening_stock_movement_reconciles(
    client: AsyncClient, reconciler: InventoryReconciliationService
) -> None:
    _, headers = await _signup(client, "one")
    product = await _product(client, headers, "One Movement")
    await _post(client, headers, "opening-stock", product["id"], "7.500")

    report = await reconciler.reconcile()
    assert report.is_consistent is True
    assert report.movement_count == 1
    assert report.rebuilt_balance_count == report.projection_count == 1


async def test_hundreds_of_movements_are_aggregated_in_postgresql(
    client: AsyncClient,
    admin_engine: AsyncEngine,
    reconciler: InventoryReconciliationService,
) -> None:
    session, headers = await _signup(client, "hundreds")
    product = await _product(client, headers, "Bulk Movements")
    warehouse = await _warehouse(client, headers)
    await _post(client, headers, "opening-stock", product["id"], "10")

    async with admin_engine.begin() as connection:
        await set_internal_maintenance_context(connection)
        await connection.execute(
            text(
                """
                INSERT INTO stock_movements (
                    id, tenant_id, product_id, warehouse_id, movement_type,
                    quantity, unit, created_by, idempotency_key, request_hash
                )
                SELECT
                    gen_random_uuid(), :tenant_id, :product_id, :warehouse_id,
                    'STOCK_RECEIPT', 1, 'piece', :user_id,
                    'bulk-' || series, repeat('a', 64)
                FROM generate_series(1, 400) AS series
                """
            ),
            {
                "tenant_id": session["user"]["business"]["id"],
                "product_id": product["id"],
                "warehouse_id": warehouse["id"],
                "user_id": session["user"]["id"],
            },
        )
        await connection.execute(
            text(
                """
                UPDATE stock_balances
                SET available_quantity = available_quantity + 400
                WHERE tenant_id = :tenant_id
                  AND product_id = :product_id
                  AND warehouse_id = :warehouse_id
                """
            ),
            {
                "tenant_id": session["user"]["business"]["id"],
                "product_id": product["id"],
                "warehouse_id": warehouse["id"],
            },
        )

    report = await reconciler.reconcile()
    assert report.is_consistent is True
    assert report.movement_count == 401
    assert report.rebuilt_balance_count == 1


async def test_multiple_warehouses_are_reconciled_independently(
    client: AsyncClient,
    admin_engine: AsyncEngine,
    reconciler: InventoryReconciliationService,
) -> None:
    session, headers = await _signup(client, "warehouses")
    product = await _product(client, headers, "Warehouse Product")
    default = await _warehouse(client, headers)
    second = await _add_warehouse(
        admin_engine, session["user"]["business"]["id"], "Second Warehouse"
    )
    await _post(
        client,
        headers,
        "opening-stock",
        product["id"],
        "5",
        warehouse_id=default["id"],
    )
    await _post(
        client,
        headers,
        "opening-stock",
        product["id"],
        "8",
        warehouse_id=str(second),
    )

    report = await reconciler.reconcile()
    assert report.is_consistent is True
    assert report.rebuilt_balance_count == report.projection_count == 2


async def test_multiple_tenants_are_reconciled_without_merging_balances(
    client: AsyncClient, reconciler: InventoryReconciliationService
) -> None:
    for suffix, quantity in (("tenant-a", "3"), ("tenant-b", "9")):
        _, headers = await _signup(client, suffix)
        product = await _product(client, headers, f"Product {suffix}")
        await _post(client, headers, "opening-stock", product["id"], quantity)

    report = await reconciler.reconcile()
    assert report.is_consistent is True
    assert report.movement_count == 2
    assert report.rebuilt_balance_count == report.projection_count == 2


async def test_every_phase_four_movement_type_reconciles(
    client: AsyncClient, reconciler: InventoryReconciliationService
) -> None:
    _, headers = await _signup(client, "types")
    product = await _product(client, headers, "All Movement Types", unit="kg")
    operations = [
        ("opening-stock", "100", {}),
        ("stock-receipts", "20", {"remarks": "Receipt"}),
        ("adjustments", "-5", {"reason": "Count correction"}),
        ("customer-returns", "3", {"remarks": "Return"}),
        ("damage", "2", {"remarks": "Damage"}),
        ("spoilage", "1", {"remarks": "Spoilage"}),
    ]
    for path, quantity, fields in operations:
        await _post(client, headers, path, product["id"], quantity, **fields)

    report = await reconciler.reconcile()
    assert report.is_consistent is True
    assert report.movement_count == 6
    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "115.000"


async def test_reconciliation_snapshot_stays_consistent_during_concurrent_posts(
    client: AsyncClient, reconciler: InventoryReconciliationService
) -> None:
    _, headers = await _signup(client, "concurrent-report")
    product = await _product(client, headers, "Concurrent Report")
    await _post(client, headers, "opening-stock", product["id"], "1")

    report, *responses = await asyncio.gather(
        reconciler.reconcile(),
        *[
            client.post(
                "/api/v1/inventory/stock-receipts",
                headers={**headers, "Idempotency-Key": f"concurrent-{number}"},
                json={"product_id": product["id"], "quantity": "1"},
            )
            for number in range(20)
        ],
    )
    assert report.is_consistent is True
    assert all(response.status_code == 201 for response in responses)
    final = await reconciler.reconcile()
    assert final.is_consistent is True
    assert final.movement_count == 21


async def test_projection_comparison_reports_missing_extra_and_mismatch(
    client: AsyncClient,
    admin_engine: AsyncEngine,
    reconciler: InventoryReconciliationService,
) -> None:
    session, headers = await _signup(client, "comparison")
    warehouse = await _warehouse(client, headers)
    mismatch_product = await _product(client, headers, "Mismatch Product")
    missing_product = await _product(client, headers, "Missing Product")
    extra_product = await _product(client, headers, "Extra Product")
    await _post(client, headers, "opening-stock", mismatch_product["id"], "5")
    await _post(client, headers, "opening-stock", missing_product["id"], "7")

    tenant_id = session["user"]["business"]["id"]
    async with admin_engine.begin() as connection:
        await set_internal_maintenance_context(connection)
        await connection.execute(
            text(
                "UPDATE stock_balances SET available_quantity = 9 "
                "WHERE tenant_id = :tenant_id AND product_id = :product_id"
            ),
            {"tenant_id": tenant_id, "product_id": mismatch_product["id"]},
        )
        await connection.execute(
            text(
                "DELETE FROM stock_balances "
                "WHERE tenant_id = :tenant_id AND product_id = :product_id"
            ),
            {"tenant_id": tenant_id, "product_id": missing_product["id"]},
        )
        await connection.execute(
            text(
                """
                INSERT INTO stock_balances (
                    tenant_id, product_id, warehouse_id, available_quantity, updated_at
                ) VALUES (:tenant_id, :product_id, :warehouse_id, 4, now())
                """
            ),
            {
                "tenant_id": tenant_id,
                "product_id": extra_product["id"],
                "warehouse_id": warehouse["id"],
            },
        )

    report = await reconciler.reconcile()
    assert report.is_consistent is False
    assert report.discrepancy_count == 3
    assert report.missing_projections[0].product_id == UUID(missing_product["id"])
    assert report.extra_projections[0].product_id == UUID(extra_product["id"])
    mismatch = report.quantity_mismatches[0]
    assert mismatch.product_id == UUID(mismatch_product["id"])
    assert mismatch.rebuilt_quantity == 5
    assert mismatch.projected_quantity == 9
    assert mismatch.difference == 4


async def test_explicit_rebuild_replaces_projections_without_changing_movements(
    client: AsyncClient,
    admin_engine: AsyncEngine,
    reconciler: InventoryReconciliationService,
) -> None:
    session, headers = await _signup(client, "rebuild")
    warehouse = await _warehouse(client, headers)
    product = await _product(client, headers, "Rebuild Product")
    extra = await _product(client, headers, "Rebuild Extra")
    await _post(client, headers, "opening-stock", product["id"], "5")
    await _post(client, headers, "stock-receipts", product["id"], "2")
    tenant_id = session["user"]["business"]["id"]
    async with admin_engine.begin() as connection:
        await set_internal_maintenance_context(connection)
        before_movements = (
            await connection.execute(
                text("SELECT id, quantity FROM stock_movements ORDER BY id")
            )
        ).all()
        await connection.execute(
            text("UPDATE stock_balances SET available_quantity = 99")
        )
        await connection.execute(
            text(
                """
                INSERT INTO stock_balances (
                    tenant_id, product_id, warehouse_id, available_quantity, updated_at
                ) VALUES (:tenant_id, :product_id, :warehouse_id, 1, now())
                """
            ),
            {
                "tenant_id": tenant_id,
                "product_id": extra["id"],
                "warehouse_id": warehouse["id"],
            },
        )

    result = await reconciler.rebuild()
    assert result.before.is_consistent is False
    assert result.after.is_consistent is True
    assert result.deleted_projection_count == 2
    assert result.created_projection_count == 1
    async with admin_engine.connect() as connection:
        await set_internal_maintenance_context(connection)
        after_movements = (
            await connection.execute(
                text("SELECT id, quantity FROM stock_movements ORDER BY id")
            )
        ).all()
    assert after_movements == before_movements

    current = await client.get(
        f"/api/v1/inventory/stock/{product['id']}", headers=headers
    )
    assert current.json()["available_quantity"] == "7.000"


async def test_rebuild_and_concurrent_posts_finish_consistently(
    client: AsyncClient,
    admin_engine: AsyncEngine,
    reconciler: InventoryReconciliationService,
) -> None:
    _, headers = await _signup(client, "concurrent-rebuild")
    product = await _product(client, headers, "Concurrent Rebuild")
    await _post(client, headers, "opening-stock", product["id"], "1")
    async with admin_engine.begin() as connection:
        await set_internal_maintenance_context(connection)
        await connection.execute(
            text("UPDATE stock_balances SET available_quantity = 0")
        )

    rebuild, *responses = await asyncio.gather(
        reconciler.rebuild(),
        *[
            client.post(
                "/api/v1/inventory/stock-receipts",
                headers={**headers, "Idempotency-Key": f"rebuild-post-{number}"},
                json={"product_id": product["id"], "quantity": "1"},
            )
            for number in range(10)
        ],
    )
    assert rebuild.after.is_consistent is True
    assert all(response.status_code == 201 for response in responses)
    final = await reconciler.reconcile()
    assert final.is_consistent is True
    assert final.movement_count == 11


async def test_negative_movement_total_is_reported_and_blocks_rebuild(
    client: AsyncClient,
    admin_engine: AsyncEngine,
    reconciler: InventoryReconciliationService,
) -> None:
    session, headers = await _signup(client, "negative")
    product = await _product(client, headers, "Negative History")
    warehouse = await _warehouse(client, headers)
    async with admin_engine.begin() as connection:
        await set_internal_maintenance_context(connection)
        await connection.execute(
            text(
                """
                INSERT INTO stock_movements (
                    id, tenant_id, product_id, warehouse_id, movement_type,
                    quantity, unit, created_by, idempotency_key, request_hash
                ) VALUES (
                    gen_random_uuid(), :tenant_id, :product_id, :warehouse_id,
                    'STOCK_ADJUSTMENT', -5, 'piece', :user_id,
                    'corrupt-negative', repeat('b', 64)
                )
                """
            ),
            {
                "tenant_id": session["user"]["business"]["id"],
                "product_id": product["id"],
                "warehouse_id": warehouse["id"],
                "user_id": session["user"]["id"],
            },
        )

    report = await reconciler.reconcile()
    assert report.is_consistent is False
    assert report.negative_balances[0].source == "movement_history"
    assert report.negative_balances[0].quantity == -5
    with pytest.raises(RebuildBlockedError):
        await reconciler.rebuild()


async def test_invalid_product_and_warehouse_references_are_reported(
    client: AsyncClient,
    admin_engine: AsyncEngine,
    reconciler: InventoryReconciliationService,
) -> None:
    session, _ = await _signup(client, "invalid-reference")
    movement_id = uuid4()
    invalid_product = uuid4()
    invalid_warehouse = uuid4()
    async with admin_engine.begin() as connection:
        await set_internal_maintenance_context(connection)
        await connection.execute(text("ALTER TABLE stock_movements DISABLE TRIGGER USER"))
        await connection.execute(
            text(
                "ALTER TABLE stock_movements "
                "DROP CONSTRAINT fk_stock_movements_product_id_products"
            )
        )
        await connection.execute(
            text("ALTER TABLE stock_movements DROP CONSTRAINT fk_stock_movements_tenant_warehouse")
        )
        await connection.execute(
            text(
                """
                INSERT INTO stock_movements (
                    id, tenant_id, product_id, warehouse_id, movement_type,
                    quantity, unit, created_by, idempotency_key, request_hash
                ) VALUES (
                    :id, :tenant_id, :product_id, :warehouse_id,
                    'STOCK_RECEIPT', 1, 'piece', :user_id,
                    'invalid-references', repeat('c', 64)
                )
                """
            ),
            {
                "id": movement_id,
                "tenant_id": session["user"]["business"]["id"],
                "product_id": invalid_product,
                "warehouse_id": invalid_warehouse,
                "user_id": session["user"]["id"],
            },
        )
        await connection.execute(
            text(
                """
                ALTER TABLE stock_movements
                ADD CONSTRAINT fk_stock_movements_product_id_products
                FOREIGN KEY (product_id)
                REFERENCES products(id)
                ON DELETE RESTRICT
                NOT VALID
                """
            )
        )
        await connection.execute(
            text(
                """
                ALTER TABLE stock_movements
                ADD CONSTRAINT fk_stock_movements_tenant_warehouse
                FOREIGN KEY (tenant_id, warehouse_id)
                REFERENCES warehouses(tenant_id, id)
                ON DELETE RESTRICT
                NOT VALID
                """
            )
        )
        await connection.execute(text("ALTER TABLE stock_movements ENABLE TRIGGER USER"))

    report = await reconciler.reconcile()
    assert report.invalid_product_references[0].movement_id == movement_id
    assert report.invalid_product_references[0].source == "movement_history"
    assert report.invalid_product_references[0].reference_id == invalid_product
    assert report.invalid_warehouse_references[0].movement_id == movement_id
    assert report.invalid_warehouse_references[0].reference_id == invalid_warehouse
    with pytest.raises(RebuildBlockedError):
        await reconciler.rebuild()


async def test_invalid_projection_references_are_reported_and_rebuildable(
    client: AsyncClient,
    admin_engine: AsyncEngine,
    reconciler: InventoryReconciliationService,
) -> None:
    session, _ = await _signup(client, "invalid-projection-reference")
    invalid_product = uuid4()
    invalid_warehouse = uuid4()
    async with admin_engine.begin() as connection:
        await set_internal_maintenance_context(connection)
        await connection.execute(text("ALTER TABLE stock_balances DISABLE TRIGGER USER"))
        await connection.execute(
            text("ALTER TABLE stock_balances DROP CONSTRAINT fk_stock_balances_product_id_products")
        )
        await connection.execute(
            text("ALTER TABLE stock_balances DROP CONSTRAINT fk_stock_balances_tenant_warehouse")
        )
        await connection.execute(
            text(
                """
                INSERT INTO stock_balances (
                    tenant_id, product_id, warehouse_id,
                    available_quantity, updated_at
                ) VALUES (
                    :tenant_id, :product_id, :warehouse_id, 1, now()
                )
                """
            ),
            {
                "tenant_id": session["user"]["business"]["id"],
                "product_id": invalid_product,
                "warehouse_id": invalid_warehouse,
            },
        )
        await connection.execute(
            text(
                """
                ALTER TABLE stock_balances
                ADD CONSTRAINT fk_stock_balances_product_id_products
                FOREIGN KEY (product_id)
                REFERENCES products(id)
                ON DELETE RESTRICT
                NOT VALID
                """
            )
        )
        await connection.execute(
            text(
                """
                ALTER TABLE stock_balances
                ADD CONSTRAINT fk_stock_balances_tenant_warehouse
                FOREIGN KEY (tenant_id, warehouse_id)
                REFERENCES warehouses(tenant_id, id)
                ON DELETE RESTRICT
                NOT VALID
                """
            )
        )
        await connection.execute(text("ALTER TABLE stock_balances ENABLE TRIGGER USER"))

    report = await reconciler.reconcile()
    assert report.invalid_product_references[0].source == "projection"
    assert report.invalid_product_references[0].movement_id is None
    assert report.invalid_warehouse_references[0].source == "projection"
    result = await reconciler.rebuild()
    assert result.after.is_consistent is True
    assert result.deleted_projection_count == 1
    assert result.created_projection_count == 0


async def test_cli_report_entry_point_returns_machine_readable_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = await _run(rebuild=False)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["is_consistent"] is True
    assert payload["movement_count"] == 0


async def test_cli_report_returns_discrepancy_exit_code(
    client: AsyncClient,
    admin_engine: AsyncEngine,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session, headers = await _signup(client, "cli-discrepancy")
    product = await _product(client, headers, "CLI Extra Projection")
    warehouse = await _warehouse(client, headers)
    async with admin_engine.begin() as connection:
        await set_internal_maintenance_context(connection)
        await connection.execute(
            text(
                """
                INSERT INTO stock_balances (
                    tenant_id, product_id, warehouse_id,
                    available_quantity, updated_at
                ) VALUES (
                    :tenant_id, :product_id, :warehouse_id, 1, now()
                )
                """
            ),
            {
                "tenant_id": session["user"]["business"]["id"],
                "product_id": product["id"],
                "warehouse_id": warehouse["id"],
            },
        )

    capsys.readouterr()
    exit_code = await _run(rebuild=False)
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["is_consistent"] is False
    assert len(payload["extra_projections"]) == 1
