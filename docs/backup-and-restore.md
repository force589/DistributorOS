# PostgreSQL backup and restore runbook

Use the managed provider's encrypted automated backups where available, plus regular logical backups for portability. The examples below use standard PostgreSQL tools and make no provider assumptions.

## Backup

1. Choose a low-traffic period and record the application version, migration revision and UTC timestamp.
2. Run `pg_dump --format=custom --no-owner --no-acl --file=distributoros-YYYYMMDDTHHMMSSZ.dump "$DATABASE_ADMIN_URL"`.
3. Encrypt the artifact, store it outside the primary database environment, and record its checksum and retention expiry.
4. Verify with `pg_restore --list distributoros-YYYYMMDDTHHMMSSZ.dump`.
5. Monitor backup age and alert if the recovery-point objective is exceeded.

Never place database URLs or plaintext backup artifacts in logs, tickets, source control or application storage.

## Restore drill

1. Create an isolated empty PostgreSQL database with the required extensions and roles.
2. Run `pg_restore --exit-on-error --clean --if-exists --no-owner --no-acl --dbname="$RESTORE_DATABASE_ADMIN_URL" distributoros-YYYYMMDDTHHMMSSZ.dump`.
3. Run `alembic upgrade head` using the restored database.
4. Point a non-production API instance at the restore.
5. Verify `/health/ready`, authentication, cross-tenant isolation, record counts, invoices, inventory reconciliation and ledger reconciliation.
6. Compare critical table counts and financial totals with the source backup manifest.
7. Destroy the isolated restore securely after sign-off.

Perform and document restore drills at least quarterly. A backup is not considered valid until a restore drill succeeds.
