# DistributorOS free-tier deployment runbook

This runbook prepares a staging/public-beta deployment with:

- Expo Web static export on Cloudflare Pages.
- FastAPI on one Render free Web Service.
- Supabase PostgreSQL used only as managed PostgreSQL.
- GitHub Actions for verification.

The application architecture remains unchanged: internal email/password auth, global
users, businesses, memberships, SQLAlchemy/Alembic, and PostgreSQL Row Level Security
(RLS). The Expo app never receives database credentials or Supabase service-role keys.

## Environment summary

| Component | Variable | Secret | Purpose |
| --- | --- | --- | --- |
| API | `ENVIRONMENT` | No | `preview` for this free-tier staging deployment. |
| API | `DATABASE_URL` | Yes | Runtime role URL for `distributoros_runtime`. |
| API | `DATABASE_MIGRATION_URL` | Yes | Migrator/owner role URL for Alembic. |
| API | `DATABASE_ADMIN_URL` | Yes | Optional maintenance URL; use the migrator URL on free tier. |
| API | `DATABASE_POOL_SIZE` | No | Default `3` for a small hosted database. |
| API | `DATABASE_MAX_OVERFLOW` | No | Default `2`. |
| API | `DATABASE_POOL_RECYCLE_SECONDS` | No | Default `1800`. |
| API | `JWT_SECRET` | Yes | At least 32 random characters. |
| API | `CORS_ORIGINS` | No | Exact JSON list of deployed web origins. No wildcard. |
| API | `COOKIE_SECURE` | No | `true` for HTTPS preview/production. |
| API | `COOKIE_SAMESITE` | No | `none` for cross-site Cloudflare Pages to Render cookies. |
| API | `PASSWORD_RESET_URL_BASE` | No | HTTPS web URL ending in `/reset-password`. |
| API | `SMTP_*` | Yes where populated | Password reset delivery settings. |
| Web/native | `EXPO_PUBLIC_APP_ENV` | No | `production` for public static build. |
| Web/native | `EXPO_PUBLIC_WEB_API_URL` | No | `https://distributoros-api.onrender.com/api/v1`. |
| Web/native | `EXPO_PUBLIC_ANDROID_API_URL` | No | Same Render API URL for public beta. |
| Web/native | `EXPO_PUBLIC_IOS_API_URL` | No | Same Render API URL for public beta. |

## 1. Supabase PostgreSQL

1. Create a Supabase project.
2. Open the database connection settings.
3. Record:
   - a direct connection URL for migrations;
   - the runtime URL for the API role created below.
4. Keep SSL enabled. DistributorOS accepts provider URLs containing
   `sslmode=require` and normalizes them for `asyncpg`.
5. Open the SQL editor and run [infra/supabase/roles.sql](../infra/supabase/roles.sql)
   after replacing both placeholder passwords.
6. Use the `distributoros_migrator` URL as `DATABASE_MIGRATION_URL`.
7. Use the `distributoros_runtime` URL as `DATABASE_URL`.
8. Deploy/run Alembic once:

   ```bash
   cd services/api
   alembic upgrade head
   ```

9. Run the grants section in [infra/supabase/roles.sql](../infra/supabase/roles.sql)
   again after migrations. It is safe to repeat and gives the runtime role ordinary
   table/sequence privileges without ownership.
10. Connect as `distributoros_runtime` and run
    [infra/supabase/verify-rls.sql](../infra/supabase/verify-rls.sql).
    Expected result:
    - `is_superuser=false`
    - `bypasses_rls=false`
    - `runtime_owned_rls_tables=0`
    - `inactive_rls_tables=0`
    - `unforced_rls_tables=0`
    - `policyless_rls_tables=0`

If Supabase prevents role creation in your project, stop and do not run the API with
a superuser or `BYPASSRLS` role. The API startup validation intentionally rejects
runtime roles that can bypass RLS or that own RLS-protected tables.

## 2. Render backend

The repository includes [render.yaml](../render.yaml). Create a Render Blueprint
from the GitHub repository, or configure a Web Service manually:

| Setting | Value |
| --- | --- |
| Service type | Web Service |
| Runtime | Docker |
| Root directory | `services/api` |
| Dockerfile path | `./Dockerfile` |
| Health check path | `/health/ready` |
| Auto-deploy | Off |
| Start command | Dockerfile `CMD` |

Set these environment variables in Render:

```text
ENVIRONMENT=preview
DATABASE_URL=<Supabase distributoros_runtime URL>
DATABASE_MIGRATION_URL=<Supabase distributoros_migrator direct URL>
JWT_SECRET=<32+ character random value>
CORS_ORIGINS=["https://<cloudflare-project>.pages.dev"]
COOKIE_SECURE=true
COOKIE_SAMESITE=none
PASSWORD_RESET_URL_BASE=https://<cloudflare-project>.pages.dev/reset-password
DATABASE_POOL_SIZE=3
DATABASE_MAX_OVERFLOW=2
DATABASE_POOL_RECYCLE_SECONDS=1800
INVOICE_PDF_ROOT=/tmp/distributoros-invoices
RATE_LIMIT_ENABLED=true
```

Optional password reset delivery variables:

```text
SMTP_HOST=<smtp host>
SMTP_PORT=587
SMTP_USERNAME=<smtp username>
SMTP_PASSWORD=<smtp password>
SMTP_FROM_EMAIL=<verified sender>
SMTP_STARTTLS=true
```

Render free Web Services do not support pre-deploy commands for migrations. Run the
manual GitHub Actions migration workflow first, confirm it succeeds, then deploy
the Render service manually.

After deploy:

1. Open `https://distributoros-api.onrender.com/health/live`.
2. Open `https://distributoros-api.onrender.com/health/ready`.
3. Confirm Render logs do not print database URLs, JWTs, cookies, or passwords.
4. Let the free service sleep, then open the web app and confirm session restore
   shows a retryable network/cold-start state instead of an authentication failure.

## 3. Cloudflare Pages frontend

Create a Cloudflare Pages project from GitHub.

| Setting | Value |
| --- | --- |
| Root directory | repository root |
| Build command | `npm ci && npm run export:web --workspace @distributoros/mobile` |
| Build output directory | `apps/mobile/dist` |
| Production branch | `main` |

Environment variables:

```text
EXPO_PUBLIC_APP_ENV=production
EXPO_PUBLIC_WEB_API_URL=https://distributoros-api.onrender.com/api/v1
EXPO_PUBLIC_ANDROID_API_URL=https://distributoros-api.onrender.com/api/v1
EXPO_PUBLIC_IOS_API_URL=https://distributoros-api.onrender.com/api/v1
```

The export script copies:

- `_redirects` for Expo Router SPA fallback so deep links refresh correctly.
- `_headers` for baseline browser security headers.

After Cloudflare gives you the Pages URL, add it to backend `CORS_ORIGINS` and
redeploy the Render API. Do not use wildcard CORS with credentials.

## 4. GitHub Actions

The CI workflow uses:

- Node 24.
- Python 3.13.
- PostgreSQL service container.
- A migrator role for Alembic.
- A separate runtime role for application tests.

Required GitHub environment secrets for the manual migration workflow:

- `DATABASE_URL`
- `DATABASE_MIGRATION_URL`
- `JWT_SECRET`

Run `DistributorOS manual database migration` with the `staging` environment before
triggering a Render deploy. Do not expose deployment secrets to pull-request jobs
from forks. The current CI does not deploy PR code or run migrations against the
staging database.

## 5. End-to-end verification

Run these checks after both API and web are deployed:

1. Open the Cloudflare Pages URL.
2. Sign up Business A.
3. Confirm the app lands on the authenticated dashboard.
4. Log out.
5. Sign up Business B with a different email.
6. Confirm Business B does not show Business A data.
7. Refresh on a protected route and verify session restoration.
8. Log out and verify browser Back/Forward cannot reveal authenticated screens.
9. Try invalid credentials and malformed inputs; verify actionable messages.
10. Temporarily stop or sleep the Render service and verify cold-start/network UI.
11. Confirm the browser console has no errors.
12. Confirm HTTPS is used for web and API.
13. Confirm the refresh cookie is `HttpOnly`, `Secure`, and `SameSite=None`.
14. Confirm generated frontend assets contain no database URLs, JWT secrets, SMTP
    secrets, or Supabase service-role keys.

## 6. Backups and restore drills

Supabase free-tier projects should not be treated as having production-grade
automatic backups. Take logical backups before migrations and before public beta
data imports:

```bash
pg_dump --format=custom --no-owner --no-acl \
  --file=backups/distributoros-YYYYMMDDTHHMMSSZ.dump \
  "$DATABASE_MIGRATION_URL"
```

Verify the artifact:

```bash
pg_restore --list backups/distributoros-YYYYMMDDTHHMMSSZ.dump
```

Restore drill into an empty non-production database:

```bash
pg_restore --exit-on-error --clean --if-exists --no-owner --no-acl \
  --dbname="$RESTORE_DATABASE_MIGRATION_URL" \
  backups/distributoros-YYYYMMDDTHHMMSSZ.dump
```

An untested backup is not a recovery plan. Document the restore database, migration
revision, checksum, UTC timestamp, and verification results.

## 7. Rollback

1. Disable Cloudflare Pages deployment for the bad commit or roll back to the
   previous Pages deployment.
2. Roll back the Render service to the previous successful deploy.
3. If a migration ran, restore the latest verified backup into a fresh database.
4. Point Render to the restored database URLs.
5. Re-run `/health/ready`, RLS verification, signup/login, refresh, logout, and
   two-tenant isolation checks before reopening access.

## 8. Free-tier limitations

- Render free Web Services can cold start after inactivity.
- One free API instance is not highly available.
- App-level rate limits protect basic abuse cases but do not replace edge/gateway
  throttling for a wider launch.
- Local invoice PDF files are a cache on Render's ephemeral filesystem; the
  database snapshots remain the source of truth.
- Supabase free database limits and backup capabilities are not equivalent to a
  paid production plan.
- Email verification is not implemented. Password reset exists, but email delivery
  requires SMTP configuration and running the outbox worker.
