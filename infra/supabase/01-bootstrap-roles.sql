-- DistributorOS Supabase bootstrap.
--
-- Run once before Alembic migrations from the Supabase SQL editor/dashboard
-- database-owner context.
--
-- Replace password placeholders before execution. Do not commit real passwords.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'distributoros_migrator') THEN
    RAISE EXCEPTION
      'Role distributoros_migrator already exists. Stop and inspect the existing role manually; this hosted Supabase bootstrap script will not ALTER ROLE.';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'distributoros_runtime') THEN
    RAISE EXCEPTION
      'Role distributoros_runtime already exists. Stop and inspect the existing role manually; this hosted Supabase bootstrap script will not ALTER ROLE.';
  END IF;

  CREATE ROLE distributoros_migrator
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS
    PASSWORD '<REPLACE_WITH_STRONG_MIGRATOR_PASSWORD>';

  CREATE ROLE distributoros_runtime
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS
    PASSWORD '<REPLACE_WITH_STRONG_RUNTIME_PASSWORD>';

  EXECUTE format(
    'GRANT CONNECT ON DATABASE %I TO distributoros_migrator, distributoros_runtime',
    current_database()
  );
END
$$;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO distributoros_migrator;
GRANT USAGE ON SCHEMA public TO distributoros_runtime;
REVOKE CREATE ON SCHEMA public FROM distributoros_runtime;
