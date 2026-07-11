# DistributorOS deployment guide

DistributorOS is infrastructure-neutral. A production deployment needs PostgreSQL 16 or newer, one or more API containers, the outbox worker, durable invoice-cache storage or a disposable cache policy, TLS termination, and a static/web or native Expo release.

## Environment matrix

| Environment | API endpoint | Cookies | Password-reset URL |
| --- | --- | --- | --- |
| Development | Local absolute HTTP native URLs; `/api/v1` through the web dev proxy | May be insecure on localhost | `http://localhost:8081/reset-password` |
| Preview | Absolute HTTPS URLs for Android, iOS and web | `COOKIE_SECURE=true` | Absolute HTTPS preview URL |
| Production | Absolute HTTPS URLs for Android, iOS and web | `COOKIE_SECURE=true` | Absolute HTTPS production URL |

Set `EXPO_PUBLIC_ANDROID_API_URL`, `EXPO_PUBLIC_IOS_API_URL`, and `EXPO_PUBLIC_WEB_API_URL` in the matching EAS environment. Native startup rejects relative URLs and rejects non-HTTPS preview/production URLs. The backend rejects local CORS origins, insecure cookies, insecure reset URLs, and missing SMTP delivery configuration in production.

Required backend secrets include `DATABASE_URL`, a migration/worker database URL with only the required privileges, `JWT_SECRET`, SMTP credentials, and the allowed `CORS_ORIGINS`. Store them in the platform secret manager, never an image or repository file.

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

