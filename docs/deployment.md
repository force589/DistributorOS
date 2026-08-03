# DistributorOS deployment guide

DistributorOS is infrastructure-neutral. A production deployment needs PostgreSQL 16 or newer, one or more API containers, the outbox worker, durable invoice-cache storage or a disposable cache policy, TLS termination, and a static/web or native Expo release. For the free Cloudflare Pages + Render + Supabase staging path, use [deployment-free-tier.md](deployment-free-tier.md).

## Environment matrix

| Environment | API endpoint | Cookies | Password-reset URL |
| --- | --- | --- | --- |
| Development | Configured `EXPO_PUBLIC_*_API_URL` values | May be insecure for local-only development | Local development reset URL |
| Preview | Absolute HTTPS URLs for Android, iOS and web | `COOKIE_SECURE=true` | Absolute HTTPS preview URL |
| Production | Absolute HTTPS URLs for Android, iOS and web | `COOKIE_SECURE=true` | Absolute HTTPS production URL |

Set `EXPO_PUBLIC_ANDROID_API_URL`, `EXPO_PUBLIC_IOS_API_URL`, and `EXPO_PUBLIC_WEB_API_URL` in the matching EAS environment. Native startup rejects relative URLs and rejects non-HTTPS preview/production URLs. The backend rejects local CORS origins, insecure cookies, insecure reset URLs, and missing SMTP delivery configuration in production.

Required backend secrets include `DATABASE_URL`, `DATABASE_MIGRATION_URL`, `JWT_SECRET`, SMTP credentials when password-reset email delivery is enabled, and the allowed `CORS_ORIGINS`. Store them in the platform secret manager, never an image or repository file.

## Managed PostgreSQL roles

Use separate database roles in managed PostgreSQL deployments:

- `DATABASE_MIGRATION_URL`: owner/migrator role for Alembic migrations and maintenance.
- `DATABASE_URL`: dedicated runtime application role with `NOSUPERUSER` and `NOBYPASSRLS`.

Do not run the API with a provider owner role that can bypass RLS. On Neon, console/API-created roles can inherit `neon_superuser`, which includes `BYPASSRLS`; create the runtime role with SQL instead and grant only ordinary schema/table privileges.

Example setup, run as the database owner after choosing a strong password:

```sql
CREATE ROLE distributoros_migrator LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '<strong-migrator-password>';
CREATE ROLE distributoros_runtime LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '<strong-runtime-password>';

ALTER SCHEMA public OWNER TO distributoros_migrator;
GRANT USAGE, CREATE ON SCHEMA public TO distributoros_migrator;

GRANT USAGE ON SCHEMA public TO distributoros_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO distributoros_runtime;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO distributoros_runtime;

ALTER DEFAULT PRIVILEGES FOR ROLE distributoros_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO distributoros_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE distributoros_migrator IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO distributoros_runtime;
```

Use the owner/migrator connection string for `DATABASE_MIGRATION_URL` and the `distributoros_runtime` connection string for `DATABASE_URL`.

## Web hosting

For the Cloudflare Pages public beta, build the Expo web app and publish
`apps/mobile/dist`. Static-site environment variables are build-time values, so
every `EXPO_PUBLIC_*` value must be set before the export command runs.

Build command:

```bash
npm ci && npm run export:web --workspace @distributoros/mobile
```

Publish directory:

```text
apps/mobile/dist
```

Environment variables:

```env
EXPO_PUBLIC_APP_ENV=production
EXPO_PUBLIC_WEB_API_URL=https://distributoros-api.onrender.com/api/v1
EXPO_PUBLIC_ANDROID_API_URL=https://distributoros-api.onrender.com/api/v1
EXPO_PUBLIC_IOS_API_URL=https://distributoros-api.onrender.com/api/v1
```

No API proxy is required for the current public beta deployment. Configure the backend
`CORS_ORIGINS` value to include the deployed frontend origin.

The export script copies Cloudflare `_redirects` and `_headers` files into
`apps/mobile/dist` so direct navigation and browser refreshes on client-routed
screens work without a server.

## Release sequence

1. Build the immutable API image from `services/api/Dockerfile`.
2. Back up PostgreSQL and verify the backup artifact.
3. Run `alembic upgrade head` once as a release job.
4. Deploy the API and wait for `/health/ready`.
5. Deploy `distributoros-outbox-worker` using the same image and environment.
6. Build web/native clients with the matching API URLs.
7. Run an authenticated smoke test, password-reset delivery test, tenant-isolation probe, and invoice download test.
8. Monitor HTTP error rate, latency, database saturation, rate-limit events and outbox backlog.

Run Uvicorn behind a trusted TLS proxy. Configure forwarded headers only for the proxy's known network; never trust forwarded headers from the public internet. Scale API instances horizontally because application state is in PostgreSQL. Run multiple outbox workers safely; `SKIP LOCKED` prevents duplicate claims.

## Health and monitoring

- `/health/live` proves the process is responsive.
- `/health/ready` proves PostgreSQL connectivity.
- Alert on readiness failure, elevated 5xx/429 rates, p95 latency, connection-pool pressure, PostgreSQL disk/replication lag, failed authentication spikes, and unprocessed/failed outbox events.
- Forward structured JSON logs to the platform log service and retain request IDs.
- Add external uptime probes and an error-tracking service without putting secrets or customer data in events.

Invoice PDFs are reproducible from immutable snapshots. Local PDF files are a cache; either mount durable shared storage or permit regeneration on each instance. Do not treat cached files as the financial source of truth.
