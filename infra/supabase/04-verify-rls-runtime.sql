-- DistributorOS Supabase runtime behavioural RLS verification.
--
-- Run after 03-verify-rls-admin.sql using the same database role configured as
-- the API DATABASE_URL: distributoros_runtime.
--
-- This script creates sample A/B tenant rows inside a transaction and rolls
-- everything back. It must not leave persistent test data behind.

BEGIN;

DO $$
DECLARE
  failures text[] := ARRAY[]::text[];
  tenant_a uuid := gen_random_uuid();
  tenant_b uuid := gen_random_uuid();
  user_a uuid := gen_random_uuid();
  user_b uuid := gen_random_uuid();
  customer_a uuid := gen_random_uuid();
  customer_b uuid := gen_random_uuid();
  product_a uuid := gen_random_uuid();
  product_b uuid := gen_random_uuid();
  sale_b uuid := gen_random_uuid();
  sale_item_b uuid := gen_random_uuid();
  warehouse_a uuid;
  row_count bigint;
BEGIN
  BEGIN
  PERFORM set_config('app.current_user_id', user_a::text, true);
  PERFORM set_config('app.current_tenant_id', tenant_a::text, true);
  PERFORM set_config('app.internal_maintenance', 'false', true);

  INSERT INTO users (id, email, password_hash)
  VALUES (user_a, 'rls-a-' || user_a::text || '@example.invalid', 'test-password-hash');
  INSERT INTO businesses (id, business_name)
  VALUES (tenant_a, 'RLS Test Business A');
  INSERT INTO memberships (business_id, user_id, role)
  VALUES (tenant_a, user_a, 'owner');
  INSERT INTO customers (
    id, tenant_id, customer_code, name, created_by, updated_by
  )
  VALUES (
    customer_a, tenant_a, 'RLS-A', 'RLS Customer A', user_a, user_a
  );
  INSERT INTO products (
    id, tenant_id, product_code, name, selling_price, unit,
    low_stock_threshold, created_by, updated_by
  )
  VALUES (
    product_a, tenant_a, 'RLS-PA', 'RLS Product A', 10.00, 'kg',
    0.000, user_a, user_a
  );

  PERFORM set_config('app.current_user_id', user_b::text, true);
  PERFORM set_config('app.current_tenant_id', tenant_b::text, true);

  INSERT INTO users (id, email, password_hash)
  VALUES (user_b, 'rls-b-' || user_b::text || '@example.invalid', 'test-password-hash');
  INSERT INTO businesses (id, business_name)
  VALUES (tenant_b, 'RLS Test Business B');
  INSERT INTO memberships (business_id, user_id, role)
  VALUES (tenant_b, user_b, 'owner');
  INSERT INTO customers (
    id, tenant_id, customer_code, name, created_by, updated_by
  )
  VALUES (
    customer_b, tenant_b, 'RLS-B', 'RLS Customer B', user_b, user_b
  );
  INSERT INTO products (
    id, tenant_id, product_code, name, selling_price, unit,
    low_stock_threshold, created_by, updated_by
  )
  VALUES (
    product_b, tenant_b, 'RLS-PB', 'RLS Product B', 10.00, 'kg',
    0.000, user_b, user_b
  );
  INSERT INTO sales (
    id, tenant_id, sale_number, customer_id, status, subtotal,
    created_by, create_idempotency_key, create_request_hash
  )
  VALUES (
    sale_b, tenant_b, 'RLS-SALE-B', customer_b, 'DRAFT', 10.00,
    user_b, 'rls-sale-b-' || sale_b::text,
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
  );
  INSERT INTO sale_items (
    id, sale_id, product_id, line_number, quantity, unit_price, line_total,
    product_name_snapshot, unit_snapshot
  )
  VALUES (
    sale_item_b, sale_b, product_b, 1, 1.000, 10.00, 10.00,
    'RLS Product B', 'kg'
  );

  PERFORM set_config('app.current_user_id', user_a::text, true);
  PERFORM set_config('app.current_tenant_id', tenant_a::text, true);

  SELECT id INTO warehouse_a
  FROM warehouses
  WHERE tenant_id = tenant_a
    AND is_default IS TRUE;

  IF warehouse_a IS NULL THEN
    failures := array_append(failures, 'Default warehouse was not created for tenant A.');
  END IF;

  PERFORM set_config('app.current_user_id', '', true);
  PERFORM set_config('app.current_tenant_id', '', true);
  PERFORM set_config('app.internal_maintenance', 'false', true);

  SELECT count(*) INTO row_count FROM customers;
  IF row_count <> 0 THEN
    failures := array_append(failures, format('No tenant context exposed %s customer row(s).', row_count));
  END IF;

  PERFORM set_config('app.current_user_id', gen_random_uuid()::text, true);
  PERFORM set_config('app.current_tenant_id', gen_random_uuid()::text, true);

  SELECT count(*) INTO row_count FROM customers;
  IF row_count <> 0 THEN
    failures := array_append(failures, format('Invalid tenant context exposed %s customer row(s).', row_count));
  END IF;

  PERFORM set_config('app.current_user_id', '', true);
  PERFORM set_config('app.current_tenant_id', '', true);
  PERFORM set_config('app.internal_maintenance', 'true', true);

  SELECT count(*) INTO row_count FROM customers;
  IF row_count <> 0 THEN
    failures := array_append(failures, format('Runtime maintenance flag exposed %s customer row(s).', row_count));
  END IF;

  PERFORM set_config('app.internal_maintenance', 'false', true);
  PERFORM set_config('app.current_user_id', user_a::text, true);
  PERFORM set_config('app.current_tenant_id', tenant_a::text, true);

  SELECT count(*) INTO row_count FROM customers WHERE id = customer_b;
  IF row_count <> 0 THEN
    failures := array_append(failures, 'Tenant A can read Tenant B customer.');
  END IF;

  BEGIN
    INSERT INTO customers (
      id, tenant_id, customer_code, name, created_by, updated_by
    )
    VALUES (
      gen_random_uuid(), tenant_b, 'RLS-CROSS', 'Cross Tenant Customer',
      user_b, user_b
    );
    failures := array_append(failures, 'Tenant A inserted a Tenant B customer.');
  EXCEPTION
    WHEN insufficient_privilege OR check_violation OR foreign_key_violation THEN
      NULL;
  END;

  UPDATE customers
  SET notes = 'cross tenant update should not apply'
  WHERE id = customer_b;
  GET DIAGNOSTICS row_count = ROW_COUNT;
  IF row_count <> 0 THEN
    failures := array_append(failures, 'Tenant A updated Tenant B customer.');
  END IF;

  DELETE FROM sale_items WHERE id = sale_item_b;
  GET DIAGNOSTICS row_count = ROW_COUNT;
  IF row_count <> 0 THEN
    failures := array_append(failures, 'Tenant A deleted Tenant B sale item.');
  END IF;

  IF warehouse_a IS NOT NULL THEN
    BEGIN
      INSERT INTO stock_movements (
        id, tenant_id, product_id, warehouse_id, movement_type,
        quantity, unit, created_by, idempotency_key, request_hash
      )
      VALUES (
        gen_random_uuid(), tenant_a, product_b, warehouse_a, 'STOCK_RECEIPT',
        1.000, 'kg', user_a, 'rls-cross-stock-' || product_b::text,
        'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
      );
      failures := array_append(failures, 'Tenant A inserted a stock movement referencing Tenant B product.');
    EXCEPTION
      WHEN insufficient_privilege OR check_violation OR foreign_key_violation THEN
        NULL;
    END;
  END IF;

    RAISE EXCEPTION 'DistributorOS runtime RLS fixture rollback.'
      USING ERRCODE = 'P7001';
  EXCEPTION
    WHEN SQLSTATE 'P7001' THEN
      NULL;
  END;

  IF cardinality(failures) > 0 THEN
    RAISE EXCEPTION 'DistributorOS runtime RLS verification failed:%', E'\n- ' || array_to_string(failures, E'\n- ');
  END IF;
END
$$;

ROLLBACK;

BEGIN;

DO $$
BEGIN
  IF NULLIF(current_setting('app.current_tenant_id', true), '') IS NOT NULL THEN
    RAISE EXCEPTION 'Transaction-local tenant context leaked after rollback.';
  END IF;

  IF NULLIF(current_setting('app.current_user_id', true), '') IS NOT NULL THEN
    RAISE EXCEPTION 'Transaction-local user context leaked after rollback.';
  END IF;

  IF current_setting('app.internal_maintenance', true) = 'true' THEN
    RAISE EXCEPTION 'Transaction-local maintenance context leaked after rollback.';
  END IF;
END
$$;

ROLLBACK;

SELECT
  'PASS' AS status,
  current_user AS verified_runtime_role,
  'DistributorOS runtime RLS behavioural verification passed without persistent test data.' AS message;
