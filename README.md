# DistributorOS

DistributorOS is a mobile-first, multi-tenant distribution management SaaS. This repository contains the approved and frozen MVP through RC-2 hardening: Expo authentication and business workflows, FastAPI domain APIs, PostgreSQL RLS, the generated API client, multi-currency presentation, English and Malayalam localization, business settings, centralized themes and design tokens, logging, abuse protection, password management, transactional delivery, error handling, exports, and tests.

Roles, permissions, subscriptions, notifications, suppliers, GST/tax, exchange-rate conversion, integrations, and other Phase 9+ functionality are intentionally absent.

## Repository layout

- `apps/mobile`: Expo app for Android, iOS, and web.
- `services/api`: FastAPI modular monolith.
- `packages/api-client`: centralized OpenAPI-generated TypeScript client.
- `infra/postgres`: local PostgreSQL role provisioning.

Copy `.env.example` to `.env` and replace every placeholder before running local services. Production secrets must come from a secret manager rather than files.

## Local development

Requirements: Node.js 24+, Python 3.12, and Docker.

1. Copy `.env.example` to `.env` and replace all placeholder secrets.
2. Install JavaScript dependencies with `npm install`.
3. Create `services/api/.venv` and install `services/api[dev]` in editable mode.
4. Start PostgreSQL with `docker compose up -d --wait`.
5. From `services/api`, apply migrations with `alembic upgrade head`.
6. Start FastAPI with `uvicorn distributoros.main:create_app --factory --reload`.
7. Start the outbox worker with `distributoros-outbox-worker` when testing password-reset email delivery.
8. Start Expo with `npm run mobile:start`.

The Android emulator normally needs `http://10.0.2.2:8000/api/v1`; iOS can use `http://localhost:8000/api/v1`; web uses `/api/v1` through the Metro development proxy. Preview and production use separately configured absolute HTTPS URLs. See `docs/deployment.md` and `docs/backup-and-restore.md`.

## Verification

- Backend: run Ruff, mypy, and pytest from `services/api`.
- Frontend: run `npm run lint`, `npm run typecheck`, and `npm run test` from the repository root.
- OpenAPI client: export the backend schema with `services/api/scripts/export_openapi.py`, then run `npm run api:generate`.
- Expo web: run `expo export --platform web` from `apps/mobile`.

Integration tests use PostgreSQL and prove that two businesses cannot read across the RLS boundary. SQLite is intentionally unsupported.

## Sales lifecycle

Sales start as editable drafts and do not affect stock. Posting a sale atomically validates inventory, creates immutable `SALE` stock movements, updates stock projections, creates an immutable `SALE` customer-ledger debit, updates the customer-balance projection, and makes the sale read-only. Voiding a posted sale creates immutable inventory and ledger reversals; it never edits or deletes history. Create, post, and void operations require idempotency keys, and sale numbers are allocated per tenant with a concurrency-safe counter.

## Customer ledger reconciliation

Customer-ledger entries are the financial source of truth. Read-only customer balances, total sales, and running balances are derived from ledger history; `customer_balance_projections` is only a rebuildable performance projection. Run the administrative, cross-tenant consistency check with:

```text
python -m distributoros.modules.ledger.reconcile_cli
```

The command reports missing, extra, mismatched, negative, and invalid-reference records as JSON. It never silently repairs discrepancies. It exits with `0` when projections are consistent, `2` when discrepancies are found, and `1` for configuration errors.

During an approved maintenance window, explicitly rebuild customer-balance projections without changing ledger history:

```text
python -m distributoros.modules.ledger.reconcile_cli --rebuild
```

Rebuild mode locks ledger writes, replaces every customer-balance projection in one transaction, verifies the rebuilt result, and never changes ledger history. It exits with `3` and rolls back if immutable ledger references are invalid, a rebuilt balance is negative, or post-rebuild verification fails.

## Inventory reconciliation

Inventory movements are the source of truth. Run the cross-tenant, read-only reconciliation with an administrative database URL:

```text
python -m distributoros.modules.inventory.reconcile_cli
```

The command prints a JSON report and exits with `0` when projections are consistent, `2` when discrepancies are found, and `1` for configuration errors.

Projection repair is never automatic. During an approved maintenance window, explicitly rebuild every projection with:

```text
python -m distributoros.modules.inventory.reconcile_cli --rebuild
```

Rebuild mode locks inventory writes, deletes and recreates projections in one transaction, verifies the rebuilt result, and never modifies movement history. It exits with `3` and rolls back if invalid movement references, negative movement totals, or a post-rebuild invariant failure are detected.
