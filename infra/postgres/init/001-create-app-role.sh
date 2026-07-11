#!/bin/sh
set -eu

psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set app_password="$DISTRIBUTOROS_APP_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE distributoros_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'distributoros_app') \gexec
SQL

