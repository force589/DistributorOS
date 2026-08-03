-- DistributorOS Supabase post-migration grants and RLS hardening.
--
-- Run after Alembic migrations have completed.
-- Required execution identity: distributoros_migrator.

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON TABLES FROM distributoros_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM distributoros_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL ON FUNCTIONS FROM distributoros_runtime;

DO $$
DECLARE
  api_role text;
  api_roles text[] := ARRAY['anon', 'authenticated', 'service_role'];
  select_tables text[] := ARRAY[
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
  object_name text;
BEGIN
  REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM PUBLIC;
  REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;

  REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM distributoros_runtime;
  REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM distributoros_runtime;

  FOREACH api_role IN ARRAY api_roles LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
      EXECUTE format('REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM %I', api_role);
      EXECUTE format('REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM %I', api_role);
    END IF;
  END LOOP;

  FOREACH object_name IN ARRAY select_tables LOOP
    IF to_regclass(format('public.%I', object_name)) IS NOT NULL THEN
      EXECUTE format('GRANT SELECT ON TABLE public.%I TO distributoros_runtime', object_name);
    END IF;
  END LOOP;

  FOREACH object_name IN ARRAY insert_tables LOOP
    IF to_regclass(format('public.%I', object_name)) IS NOT NULL THEN
      EXECUTE format('GRANT INSERT ON TABLE public.%I TO distributoros_runtime', object_name);
    END IF;
  END LOOP;

  FOREACH object_name IN ARRAY update_tables LOOP
    IF to_regclass(format('public.%I', object_name)) IS NOT NULL THEN
      EXECUTE format('GRANT UPDATE ON TABLE public.%I TO distributoros_runtime', object_name);
    END IF;
  END LOOP;

  FOREACH object_name IN ARRAY delete_tables LOOP
    IF to_regclass(format('public.%I', object_name)) IS NOT NULL THEN
      EXECUTE format('GRANT DELETE ON TABLE public.%I TO distributoros_runtime', object_name);
    END IF;
  END LOOP;

  FOREACH object_name IN ARRAY app_functions LOOP
    IF to_regprocedure(format('public.%I()', object_name)) IS NOT NULL THEN
      EXECUTE format('REVOKE ALL ON FUNCTION public.%I() FROM PUBLIC', object_name);
      EXECUTE format('REVOKE ALL ON FUNCTION public.%I() FROM distributoros_runtime', object_name);
      FOREACH api_role IN ARRAY api_roles LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
          EXECUTE format('REVOKE ALL ON FUNCTION public.%I() FROM %I', object_name, api_role);
        END IF;
      END LOOP;
    END IF;
  END LOOP;
END
$$;

-- Harden migrated RLS policies so the maintenance bypass is available only to
-- the migrator role. Runtime sessions may set custom GUC values, so the
-- maintenance flag alone must never be enough to bypass tenant isolation.
DO $$
DECLARE
  tenant_id_setting text := 'NULLIF(current_setting(''app.current_tenant_id'', true), '''')::uuid';
  user_id_setting text := 'NULLIF(current_setting(''app.current_user_id'', true), '''')::uuid';
  maintenance_check text := '(current_user = ''distributoros_migrator'' AND current_setting(''app.internal_maintenance'', true) = ''true'')';
  tenant_policy_tables text[] := ARRAY[
    'customer_code_counters',
    'customers',
    'product_code_counters',
    'products',
    'stock_movements',
    'stock_balances',
    'sale_code_counters',
    'sales',
    'customer_ledger_entries',
    'customer_balance_projections',
    'payment_number_counters',
    'payments',
    'payment_allocations',
    'invoice_number_counters',
    'invoices',
    'invoice_items'
  ];
  tenant_policy_table text;
  tenant_policy_name text;
  tenant_access_check text;
BEGIN
  IF to_regclass('public.businesses') IS NOT NULL THEN
    EXECUTE 'DROP POLICY IF EXISTS businesses_insert ON public.businesses';
    EXECUTE format(
      'CREATE POLICY businesses_insert ON public.businesses FOR INSERT WITH CHECK (%s OR businesses.id = %s)',
      maintenance_check,
      tenant_id_setting
    );

    EXECUTE 'DROP POLICY IF EXISTS businesses_select ON public.businesses';
    EXECUTE format(
      'CREATE POLICY businesses_select ON public.businesses FOR SELECT USING (%s OR (businesses.id = %s AND EXISTS (SELECT 1 FROM public.memberships WHERE memberships.business_id = businesses.id AND memberships.user_id = %s)))',
      maintenance_check,
      tenant_id_setting,
      user_id_setting
    );

    EXECUTE 'DROP POLICY IF EXISTS businesses_update ON public.businesses';
    EXECUTE format(
      'CREATE POLICY businesses_update ON public.businesses FOR UPDATE USING (%s OR (businesses.id = %s AND EXISTS (SELECT 1 FROM public.memberships WHERE memberships.business_id = businesses.id AND memberships.user_id = %s))) WITH CHECK (%s OR businesses.id = %s)',
      maintenance_check,
      tenant_id_setting,
      user_id_setting,
      maintenance_check,
      tenant_id_setting
    );
  END IF;

  IF to_regclass('public.memberships') IS NOT NULL THEN
    EXECUTE 'DROP POLICY IF EXISTS memberships_select ON public.memberships';
    EXECUTE format(
      'CREATE POLICY memberships_select ON public.memberships FOR SELECT USING (%s OR memberships.user_id = %s)',
      maintenance_check,
      user_id_setting
    );

    EXECUTE 'DROP POLICY IF EXISTS memberships_insert ON public.memberships';
    EXECUTE format(
      'CREATE POLICY memberships_insert ON public.memberships FOR INSERT WITH CHECK (%s OR (memberships.user_id = %s AND memberships.business_id = %s))',
      maintenance_check,
      user_id_setting,
      tenant_id_setting
    );
  END IF;

  IF to_regclass('public.auth_sessions') IS NOT NULL THEN
    EXECUTE 'DROP POLICY IF EXISTS auth_sessions_user_access ON public.auth_sessions';
    EXECUTE format(
      'CREATE POLICY auth_sessions_user_access ON public.auth_sessions FOR ALL USING (%s OR auth_sessions.user_id = %s) WITH CHECK (%s OR auth_sessions.user_id = %s)',
      maintenance_check,
      user_id_setting,
      maintenance_check,
      user_id_setting
    );
  END IF;

  IF to_regclass('public.warehouses') IS NOT NULL THEN
    EXECUTE 'DROP POLICY IF EXISTS warehouses_select_update ON public.warehouses';
    EXECUTE format(
      'CREATE POLICY warehouses_select_update ON public.warehouses FOR ALL USING (%s OR (warehouses.tenant_id = %s AND EXISTS (SELECT 1 FROM public.memberships WHERE memberships.business_id = warehouses.tenant_id AND memberships.user_id = %s))) WITH CHECK (%s OR warehouses.tenant_id = %s)',
      maintenance_check,
      tenant_id_setting,
      user_id_setting,
      maintenance_check,
      tenant_id_setting
    );
  END IF;

  FOREACH tenant_policy_table IN ARRAY tenant_policy_tables LOOP
    IF to_regclass(format('public.%I', tenant_policy_table)) IS NOT NULL THEN
      tenant_policy_name := tenant_policy_table || '_tenant_access';
      tenant_access_check := format(
        '%2$s OR (%1$I.tenant_id = %3$s AND EXISTS (SELECT 1 FROM public.memberships WHERE memberships.business_id = %1$I.tenant_id AND memberships.user_id = %4$s))',
        tenant_policy_table,
        maintenance_check,
        tenant_id_setting,
        user_id_setting
      );

      EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', tenant_policy_name, tenant_policy_table);
      EXECUTE format(
        'CREATE POLICY %I ON public.%I FOR ALL USING (%s) WITH CHECK (%s)',
        tenant_policy_name,
        tenant_policy_table,
        tenant_access_check,
        tenant_access_check
      );
    END IF;
  END LOOP;

  IF to_regclass('public.sale_items') IS NOT NULL THEN
    EXECUTE 'DROP POLICY IF EXISTS sale_items_tenant_access ON public.sale_items';
    EXECUTE format(
      'CREATE POLICY sale_items_tenant_access ON public.sale_items FOR ALL USING (%s OR EXISTS (SELECT 1 FROM public.sales WHERE sales.id = sale_items.sale_id AND sales.tenant_id = %s AND EXISTS (SELECT 1 FROM public.memberships WHERE memberships.business_id = sales.tenant_id AND memberships.user_id = %s))) WITH CHECK (%s OR EXISTS (SELECT 1 FROM public.sales WHERE sales.id = sale_items.sale_id AND sales.tenant_id = %s AND EXISTS (SELECT 1 FROM public.memberships WHERE memberships.business_id = sales.tenant_id AND memberships.user_id = %s)))',
      maintenance_check,
      tenant_id_setting,
      user_id_setting,
      maintenance_check,
      tenant_id_setting,
      user_id_setting
    );
  END IF;
END
$$;
