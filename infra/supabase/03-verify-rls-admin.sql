-- DistributorOS Supabase administrative RLS verification.
--
-- Run after 02-post-migration-grants.sql from the Supabase SQL editor/dashboard
-- database-owner context. This is metadata verification and does not mutate data.

DO $$
DECLARE
  expected_rls_tables text[] := ARRAY[
    'businesses',
    'memberships',
    'auth_sessions',
    'customer_code_counters',
    'customers',
    'product_code_counters',
    'products',
    'warehouses',
    'stock_movements',
    'stock_balances',
    'sale_code_counters',
    'sales',
    'sale_items',
    'customer_ledger_entries',
    'customer_balance_projections',
    'payment_number_counters',
    'payments',
    'payment_allocations',
    'invoice_number_counters',
    'invoices',
    'invoice_items'
  ];
  runtime_tables text[] := ARRAY[
    'users',
    'businesses',
    'memberships',
    'auth_sessions',
    'password_reset_tokens',
    'request_rate_limits',
    'outbox_events',
    'customer_code_counters',
    'customers',
    'product_code_counters',
    'products',
    'warehouses',
    'stock_movements',
    'stock_balances',
    'sale_code_counters',
    'sales',
    'sale_items',
    'customer_ledger_entries',
    'customer_balance_projections',
    'payment_number_counters',
    'payments',
    'payment_allocations',
    'invoice_number_counters',
    'invoices',
    'invoice_items'
  ];
  insert_tables text[] := ARRAY[
    'users',
    'businesses',
    'memberships',
    'auth_sessions',
    'password_reset_tokens',
    'request_rate_limits',
    'outbox_events',
    'customer_code_counters',
    'customers',
    'product_code_counters',
    'products',
    'stock_movements',
    'stock_balances',
    'sale_code_counters',
    'sales',
    'sale_items',
    'customer_ledger_entries',
    'customer_balance_projections',
    'payment_number_counters',
    'payments',
    'payment_allocations',
    'invoice_number_counters',
    'invoices',
    'invoice_items'
  ];
  update_tables text[] := ARRAY[
    'users',
    'businesses',
    'auth_sessions',
    'password_reset_tokens',
    'request_rate_limits',
    'outbox_events',
    'customer_code_counters',
    'customers',
    'product_code_counters',
    'products',
    'stock_balances',
    'sale_code_counters',
    'sales',
    'customer_balance_projections',
    'payment_number_counters',
    'payments',
    'invoice_number_counters',
    'invoices'
  ];
  delete_tables text[] := ARRAY['sale_items'];
  tenant_scoped_tables text[] := ARRAY[
    'businesses',
    'customer_code_counters',
    'customers',
    'product_code_counters',
    'products',
    'warehouses',
    'stock_movements',
    'stock_balances',
    'sale_code_counters',
    'sales',
    'sale_items',
    'customer_ledger_entries',
    'customer_balance_projections',
    'payment_number_counters',
    'payments',
    'payment_allocations',
    'invoice_number_counters',
    'invoices',
    'invoice_items'
  ];
  user_scoped_tables text[] := ARRAY['memberships', 'auth_sessions'];
  app_functions text[] := ARRAY[
    'create_business_default_warehouse',
    'validate_inventory_tenant_product',
    'prevent_stock_movement_mutation',
    'prevent_product_unit_change_with_stock',
    'validate_sale_customer',
    'enforce_sale_lifecycle',
    'enforce_sale_item_lifecycle',
    'validate_customer_ledger_entry',
    'enforce_customer_ledger_immutable',
    'validate_customer_balance_projection',
    'validate_payment',
    'enforce_payment_immutable',
    'validate_payment_allocation',
    'enforce_payment_allocation_immutable',
    'validate_invoice',
    'enforce_invoice_immutable',
    'validate_invoice_item',
    'enforce_invoice_item_immutable'
  ];
  managed_roles text[] := ARRAY['service_role', 'authenticated', 'anon', 'supabase_admin', 'postgres'];
  managed_schemas text[] := ARRAY['auth', 'storage', 'realtime', 'extensions'];
  failures text[] := ARRAY[]::text[];
  checked_role text;
  managed_role text;
  schema_name text;
  object_name text;
  policy_expression text;
  role_record record;
  bad_objects text[];
  migrator_role_exists boolean := false;
  runtime_role_exists boolean := false;
  public_can_execute boolean;
BEGIN
  FOR checked_role IN SELECT unnest(ARRAY['distributoros_migrator', 'distributoros_runtime']) LOOP
    SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
      INTO role_record
    FROM pg_roles
    WHERE rolname = checked_role;

    IF NOT FOUND THEN
      failures := failures || format('Role %I does not exist.', checked_role);
    ELSE
      IF checked_role = 'distributoros_migrator' THEN
        migrator_role_exists := true;
      ELSIF checked_role = 'distributoros_runtime' THEN
        runtime_role_exists := true;
      END IF;

      IF NOT role_record.rolcanlogin THEN
        failures := failures || format('Role %I is not LOGIN.', checked_role);
      END IF;
      IF role_record.rolsuper THEN
        failures := failures || format('Role %I is SUPERUSER.', checked_role);
      END IF;
      IF role_record.rolcreatedb THEN
        failures := failures || format('Role %I has CREATEDB.', checked_role);
      END IF;
      IF role_record.rolcreaterole THEN
        failures := failures || format('Role %I has CREATEROLE.', checked_role);
      END IF;
      IF role_record.rolreplication THEN
        failures := failures || format('Role %I has REPLICATION.', checked_role);
      END IF;
      IF role_record.rolbypassrls THEN
        failures := failures || format('Role %I has BYPASSRLS.', checked_role);
      END IF;
    END IF;
  END LOOP;

  IF migrator_role_exists OR runtime_role_exists THEN
    FOREACH managed_role IN ARRAY managed_roles LOOP
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = managed_role) THEN
        IF migrator_role_exists AND pg_has_role('distributoros_migrator', managed_role, 'member') THEN
        failures := failures || format('Role distributoros_migrator is a member of %I.', managed_role);
        END IF;
        IF runtime_role_exists AND pg_has_role('distributoros_runtime', managed_role, 'member') THEN
        failures := failures || format('Role distributoros_runtime is a member of %I.', managed_role);
        END IF;
      END IF;
    END LOOP;
  END IF;

  IF migrator_role_exists THEN
    IF NOT has_schema_privilege('distributoros_migrator', 'public', 'USAGE') THEN
      failures := failures || 'distributoros_migrator lacks USAGE on schema public.';
    END IF;
    IF NOT has_schema_privilege('distributoros_migrator', 'public', 'CREATE') THEN
      failures := failures || 'distributoros_migrator lacks CREATE on schema public.';
    END IF;
  END IF;
  IF runtime_role_exists THEN
    IF NOT has_schema_privilege('distributoros_runtime', 'public', 'USAGE') THEN
      failures := failures || 'distributoros_runtime lacks USAGE on schema public.';
    END IF;
    IF has_schema_privilege('distributoros_runtime', 'public', 'CREATE') THEN
      failures := failures || 'distributoros_runtime has CREATE on schema public.';
    END IF;
  END IF;

  IF migrator_role_exists OR runtime_role_exists THEN
    FOREACH schema_name IN ARRAY managed_schemas LOOP
      IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = schema_name) THEN
        IF (migrator_role_exists AND has_schema_privilege('distributoros_migrator', schema_name, 'CREATE'))
          OR (runtime_role_exists AND has_schema_privilege('distributoros_runtime', schema_name, 'CREATE')) THEN
          failures := failures || format('DistributorOS roles have CREATE on Supabase-managed schema %I.', schema_name);
        END IF;
      END IF;
    END LOOP;
  END IF;

  FOREACH object_name IN ARRAY expected_rls_tables LOOP
    IF to_regclass(format('public.%I', object_name)) IS NULL THEN
      failures := failures || format('Expected RLS table public.%I does not exist.', object_name);
    ELSE
      IF NOT EXISTS (
        SELECT 1
        FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = object_name
          AND relation.relrowsecurity
      ) THEN
        failures := failures || format('RLS is not enabled on public.%I.', object_name);
      END IF;

      IF NOT EXISTS (
        SELECT 1
        FROM pg_class relation
        JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relname = object_name
          AND relation.relforcerowsecurity
      ) THEN
        failures := failures || format('FORCE ROW LEVEL SECURITY is not enabled on public.%I.', object_name);
      END IF;

      IF NOT EXISTS (
        SELECT 1 FROM pg_policies policy
        WHERE policy.schemaname = 'public'
          AND policy.tablename = object_name
      ) THEN
        failures := failures || format('No RLS policy exists on public.%I.', object_name);
      END IF;
    END IF;
  END LOOP;

  SELECT COALESCE(array_agg(relation.relname::text ORDER BY relation.relname), ARRAY[]::text[])
    INTO bad_objects
  FROM pg_class relation
  JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
  WHERE namespace.nspname = 'public'
    AND relation.relkind IN ('r', 'p')
    AND (relation.relname = ANY(runtime_tables) OR relation.relname = 'alembic_version')
    AND pg_get_userbyid(relation.relowner) <> 'distributoros_migrator';

  IF cardinality(bad_objects) > 0 THEN
    failures := failures || format('Application tables are not owned by distributoros_migrator: %s.', array_to_string(bad_objects, ', '));
  END IF;

  IF runtime_role_exists THEN
    SELECT COALESCE(array_agg(relation.relname::text ORDER BY relation.relname), ARRAY[]::text[])
      INTO bad_objects
    FROM pg_class relation
    JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
    WHERE namespace.nspname = 'public'
      AND relation.relkind IN ('r', 'p')
      AND pg_get_userbyid(relation.relowner) = 'distributoros_runtime';

    IF cardinality(bad_objects) > 0 THEN
      failures := failures || format('distributoros_runtime owns tables: %s.', array_to_string(bad_objects, ', '));
    END IF;
  END IF;

  IF runtime_role_exists THEN
    FOREACH object_name IN ARRAY runtime_tables LOOP
      IF to_regclass(format('public.%I', object_name)) IS NOT NULL THEN
      IF NOT has_table_privilege('distributoros_runtime', format('public.%I', object_name), 'SELECT') THEN
        failures := failures || format('distributoros_runtime is missing SELECT on public.%I.', object_name);
      END IF;
      IF (object_name = ANY(insert_tables)) <> has_table_privilege('distributoros_runtime', format('public.%I', object_name), 'INSERT') THEN
        failures := failures || format('distributoros_runtime INSERT privilege mismatch on public.%I.', object_name);
      END IF;
      IF (object_name = ANY(update_tables)) <> has_table_privilege('distributoros_runtime', format('public.%I', object_name), 'UPDATE') THEN
        failures := failures || format('distributoros_runtime UPDATE privilege mismatch on public.%I.', object_name);
      END IF;
      IF (object_name = ANY(delete_tables)) <> has_table_privilege('distributoros_runtime', format('public.%I', object_name), 'DELETE') THEN
        failures := failures || format('distributoros_runtime DELETE privilege mismatch on public.%I.', object_name);
      END IF;
      IF has_table_privilege('distributoros_runtime', format('public.%I', object_name), 'TRUNCATE')
        OR has_table_privilege('distributoros_runtime', format('public.%I', object_name), 'REFERENCES')
        OR has_table_privilege('distributoros_runtime', format('public.%I', object_name), 'TRIGGER') THEN
        failures := failures || format('distributoros_runtime has structural table privilege on public.%I.', object_name);
      END IF;
      END IF;
    END LOOP;
  END IF;

  IF runtime_role_exists THEN
    SELECT COALESCE(array_agg(relation.relname::text ORDER BY relation.relname), ARRAY[]::text[])
      INTO bad_objects
    FROM pg_class relation
    JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
    WHERE namespace.nspname = 'public'
      AND relation.relkind IN ('r', 'p')
      AND relation.relname <> ALL(runtime_tables)
      AND (
        has_table_privilege('distributoros_runtime', relation.oid, 'SELECT')
        OR has_table_privilege('distributoros_runtime', relation.oid, 'INSERT')
        OR has_table_privilege('distributoros_runtime', relation.oid, 'UPDATE')
        OR has_table_privilege('distributoros_runtime', relation.oid, 'DELETE')
        OR has_table_privilege('distributoros_runtime', relation.oid, 'TRUNCATE')
        OR has_table_privilege('distributoros_runtime', relation.oid, 'REFERENCES')
        OR has_table_privilege('distributoros_runtime', relation.oid, 'TRIGGER')
      );

    IF cardinality(bad_objects) > 0 THEN
      failures := failures || format('distributoros_runtime has privileges on non-runtime tables: %s.', array_to_string(bad_objects, ', '));
    END IF;
  END IF;

  IF runtime_role_exists AND to_regclass('public.alembic_version') IS NOT NULL THEN
    IF has_table_privilege('distributoros_runtime', 'public.alembic_version', 'SELECT')
      OR has_table_privilege('distributoros_runtime', 'public.alembic_version', 'INSERT')
      OR has_table_privilege('distributoros_runtime', 'public.alembic_version', 'UPDATE')
      OR has_table_privilege('distributoros_runtime', 'public.alembic_version', 'DELETE') THEN
      failures := failures || 'distributoros_runtime has privileges on public.alembic_version.';
    END IF;
  END IF;

  IF runtime_role_exists THEN
    SELECT COALESCE(array_agg(sequence_schema || '.' || sequence_name ORDER BY sequence_schema, sequence_name), ARRAY[]::text[])
      INTO bad_objects
    FROM information_schema.sequences
    WHERE sequence_schema = 'public'
      AND (
        has_sequence_privilege('distributoros_runtime', format('%I.%I', sequence_schema, sequence_name), 'USAGE')
        OR has_sequence_privilege('distributoros_runtime', format('%I.%I', sequence_schema, sequence_name), 'SELECT')
        OR has_sequence_privilege('distributoros_runtime', format('%I.%I', sequence_schema, sequence_name), 'UPDATE')
      );

    IF cardinality(bad_objects) > 0 THEN
      failures := failures || format('distributoros_runtime has unnecessary sequence privileges: %s.', array_to_string(bad_objects, ', '));
    END IF;
  END IF;

  FOREACH object_name IN ARRAY app_functions LOOP
    IF to_regprocedure(format('public.%I()', object_name)) IS NOT NULL THEN
      IF EXISTS (
        SELECT 1
        FROM pg_proc procedure
        JOIN pg_namespace namespace ON namespace.oid = procedure.pronamespace
        WHERE namespace.nspname = 'public'
          AND procedure.proname = object_name
          AND pg_get_userbyid(procedure.proowner) <> 'distributoros_migrator'
      ) THEN
        failures := failures || format('Application function public.%I() is not owned by distributoros_migrator.', object_name);
      END IF;

      IF runtime_role_exists AND has_function_privilege('distributoros_runtime', format('public.%I()', object_name), 'EXECUTE') THEN
        failures := failures || format('distributoros_runtime can execute privileged function public.%I().', object_name);
      END IF;

      SELECT EXISTS (
        SELECT 1
        FROM pg_proc procedure
        JOIN pg_namespace namespace ON namespace.oid = procedure.pronamespace
        WHERE namespace.nspname = 'public'
          AND procedure.proname = object_name
          AND (
            procedure.proacl IS NULL
            OR EXISTS (
              SELECT 1
              FROM aclexplode(procedure.proacl) acl
              WHERE acl.grantee = 0
                AND acl.privilege_type = 'EXECUTE'
            )
          )
      ) INTO public_can_execute;

      IF public_can_execute THEN
        failures := failures || format('PUBLIC can execute privileged function public.%I().', object_name);
      END IF;
    END IF;
  END LOOP;

  SELECT COALESCE(array_agg(policy.schemaname || '.' || policy.tablename || '.' || policy.policyname ORDER BY policy.schemaname, policy.tablename, policy.policyname), ARRAY[]::text[])
    INTO bad_objects
  FROM pg_policies policy
  WHERE policy.schemaname = 'public'
    AND policy.tablename = ANY(expected_rls_tables)
    AND array_to_string(policy.roles, ',') <> 'public';

  IF cardinality(bad_objects) > 0 THEN
    failures := failures || format('RLS policies target non-PUBLIC roles: %s.', array_to_string(bad_objects, ', '));
  END IF;

  SELECT COALESCE(array_agg(policy.schemaname || '.' || policy.tablename || '.' || policy.policyname ORDER BY policy.schemaname, policy.tablename, policy.policyname), ARRAY[]::text[])
    INTO bad_objects
  FROM pg_policies policy
  WHERE policy.schemaname = 'public'
    AND policy.tablename = ANY(expected_rls_tables)
    AND policy.cmd IN ('ALL', 'INSERT', 'UPDATE')
    AND policy.with_check IS NULL;

  IF cardinality(bad_objects) > 0 THEN
    failures := failures || format('Mutation RLS policies are missing WITH CHECK: %s.', array_to_string(bad_objects, ', '));
  END IF;

  SELECT COALESCE(array_agg(policy.schemaname || '.' || policy.tablename || '.' || policy.policyname ORDER BY policy.schemaname, policy.tablename, policy.policyname), ARRAY[]::text[])
    INTO bad_objects
  FROM pg_policies policy
  WHERE policy.schemaname = 'public'
    AND policy.tablename = ANY(expected_rls_tables)
    AND lower(COALESCE(policy.qual, '') || ' ' || COALESCE(policy.with_check, '')) LIKE '%app.internal_maintenance%'
    AND lower(COALESCE(policy.qual, '') || ' ' || COALESCE(policy.with_check, '')) NOT LIKE '%distributoros_migrator%';

  IF cardinality(bad_objects) > 0 THEN
    failures := failures || format('Maintenance bypass is not restricted to distributoros_migrator in policies: %s.', array_to_string(bad_objects, ', '));
  END IF;

  FOREACH object_name IN ARRAY tenant_scoped_tables LOOP
    IF to_regclass(format('public.%I', object_name)) IS NOT NULL THEN
      SELECT lower(COALESCE(string_agg(COALESCE(policy.qual, '') || ' ' || COALESCE(policy.with_check, ''), ' '), ''))
        INTO policy_expression
      FROM pg_policies policy
      WHERE policy.schemaname = 'public'
        AND policy.tablename = object_name;

      IF policy_expression NOT LIKE '%app.current_tenant_id%' THEN
        failures := failures || format('Tenant-scoped policies for public.%I do not reference app.current_tenant_id.', object_name);
      END IF;
      IF object_name <> 'businesses' AND policy_expression NOT LIKE '%memberships%' THEN
        failures := failures || format('Tenant-scoped policies for public.%I do not enforce membership checks.', object_name);
      END IF;
    END IF;
  END LOOP;

  FOREACH object_name IN ARRAY user_scoped_tables LOOP
    IF to_regclass(format('public.%I', object_name)) IS NOT NULL THEN
      SELECT lower(COALESCE(string_agg(COALESCE(policy.qual, '') || ' ' || COALESCE(policy.with_check, ''), ' '), ''))
        INTO policy_expression
      FROM pg_policies policy
      WHERE policy.schemaname = 'public'
        AND policy.tablename = object_name;

      IF policy_expression NOT LIKE '%app.current_user_id%' THEN
        failures := failures || format('User-scoped policies for public.%I do not reference app.current_user_id.', object_name);
      END IF;
    END IF;
  END LOOP;

  IF cardinality(failures) > 0 THEN
    RAISE EXCEPTION 'DistributorOS admin RLS verification failed:%', E'\n- ' || array_to_string(failures, E'\n- ');
  END IF;
END
$$;

SELECT 'PASS' AS status, current_user AS verified_by, 'DistributorOS admin RLS verification passed.' AS message;
