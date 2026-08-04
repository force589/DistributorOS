import { describe, expect, it, vi } from 'vitest';

import { ApiClient, ApiError } from './client';

const jsonResponse = (status: number, body: unknown): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'X-Request-ID': 'request-1' },
  });

const textResponse = (status: number, body: string): Response =>
  new Response(body, {
    status,
    headers: { 'Content-Type': 'text/csv; charset=utf-8', 'X-Request-ID': 'request-1' },
  });

describe('ApiClient', () => {
  it('invokes the default browser fetch with the global receiver', async () => {
    const originalFetch = globalThis.fetch;
    const receiverSensitiveFetch = function (this: unknown): Promise<Response> {
      if (this !== globalThis) {
        throw new TypeError('Illegal invocation');
      }
      return Promise.resolve(
        jsonResponse(401, {
          error: { code: 'SESSION_EXPIRED', message: 'Session expired.' },
        }),
      );
    } as typeof fetch;
    globalThis.fetch = receiverSensitiveFetch;

    try {
      const client = new ApiClient({ baseUrl: '/api/v1', platform: 'web' });

      await expect(client.refresh(null)).rejects.toMatchObject({
        status: 401,
        code: 'SESSION_EXPIRED',
      });
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('uses credentialed browser auth requests so HttpOnly refresh cookies can persist', async () => {
    const authBody = {
      access_token: 'access-token',
      refresh_token: null,
      token_type: 'bearer',
      expires_in: 900,
      user: { id: 'user-1', business: { id: 'business-1' } },
    };
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(jsonResponse(200, authBody)),
    );
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'web',
      fetchImplementation,
    });

    await client.login({ email: 'owner@example.com', password: 'secure-password' });
    await client.refresh(null);

    expect(fetchImplementation.mock.calls.map((call) => call[0])).toEqual([
      'https://api.example.com/api/v1/auth/login',
      'https://api.example.com/api/v1/auth/refresh',
    ]);
    for (const [, init] of fetchImplementation.mock.calls) {
      expect(init?.credentials).toBe('include');
      expect((init?.headers as Headers).get('X-Client-Platform')).toBe('web');
    }
  });

  it('maps API failures centrally', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(403, {
        error: { code: 'FORBIDDEN', message: 'Permission denied.', request_id: 'request-1' },
      }),
    );
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'web',
      fetchImplementation,
    });

    const failure = await client.me().catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ status: 403, code: 'FORBIDDEN', requestId: 'request-1' });
  });

  it('retries safe startup reads when the free API is temporarily unavailable', async () => {
    const fetchImplementation = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(503, {}))
      .mockResolvedValueOnce(jsonResponse(200, { user: { id: '1' } }));
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'web',
      fetchImplementation,
      startupRetryDelaysMs: [0],
    });

    await expect(client.me()).resolves.toEqual({ user: { id: '1' } });

    expect(fetchImplementation).toHaveBeenCalledTimes(2);
  });

  it('does not retry non-idempotent writes during startup failures', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockRejectedValue(new Error('offline'));
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'web',
      fetchImplementation,
      startupRetryDelaysMs: [0, 0],
    });

    await expect(
      client.login({ email: 'owner@example.com', password: 'secure-password' }),
    ).rejects.toMatchObject({ code: 'NETWORK_ERROR' });

    expect(fetchImplementation).toHaveBeenCalledTimes(1);
  });

  it('uses the authenticated business settings endpoints', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(
        jsonResponse(200, {
          business_name: 'DistributorOS',
          currency: 'INR',
          language: 'en',
          theme: 'system',
        }),
      ),
    );
    const client = new ApiClient({
      baseUrl: '/api/v1',
      platform: 'web',
      fetchImplementation,
    });

    await client.getBusinessSettings();
    await client.updateBusinessSettings({ currency: 'USD', language: 'ml' });

    expect(fetchImplementation.mock.calls[0]?.[0]).toBe('/api/v1/business/settings');
    expect(fetchImplementation.mock.calls[1]?.[0]).toBe('/api/v1/business/settings');
    expect(fetchImplementation.mock.calls[1]?.[1]?.method).toBe('PATCH');
  });

  it.each([
    [403, 'FORBIDDEN'],
    [404, 'NOT_FOUND'],
    [422, 'VALIDATION_ERROR'],
    [500, 'INTERNAL_SERVER_ERROR'],
  ])('maps HTTP %s when an upstream body is unavailable', async (status, code) => {
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'web',
      fetchImplementation: vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(status, {})),
    });

    await expect(client.me()).rejects.toMatchObject({ status, code });
  });

  it('uses one refresh for concurrent unauthorized requests', async () => {
    let requestCount = 0;
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation(() => {
      requestCount += 1;
      return Promise.resolve(
        requestCount <= 2
          ? jsonResponse(401, { error: { code: 'SESSION_EXPIRED' } })
          : jsonResponse(200, { user: { id: '1' } }),
      );
    });
    const refresh = vi.fn().mockResolvedValue('new-access-token');
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'android',
      fetchImplementation,
    });
    client.setUnauthorizedHandler(refresh);

    await Promise.all([client.me(), client.me()]);

    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it('encodes customer list and search parameters without exposing tenant ids', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(jsonResponse(200, { items: [], has_more: false, page_size: 0 })),
    );
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'web',
      fetchImplementation,
    });

    await client.listCustomers({
      status: 'archived',
      sort: 'name_desc',
      search: 'A&B',
      limit: 25,
      cursor: 'next page',
    });
    await client.searchCustomers('CUST-000001');

    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      'https://api.example.com/api/v1/customers?status=archived&sort=name_desc&search=A%26B&limit=25&cursor=next+page',
    );
    expect(fetchImplementation.mock.calls[1]?.[0]).toBe(
      'https://api.example.com/api/v1/customers/search?q=CUST-000001',
    );
  });

  it('uses the expected customer mutation endpoints', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(jsonResponse(200, { customer: { id: 'customer-1' } })),
    );
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'android',
      fetchImplementation,
    });

    await client.updateCustomer('customer/1', { name: 'Updated' });
    await client.archiveCustomer('customer/1');
    await client.restoreCustomer('customer/1');

    expect(fetchImplementation.mock.calls.map((call) => call[0])).toEqual([
      'https://api.example.com/api/v1/customers/customer%2F1',
      'https://api.example.com/api/v1/customers/customer%2F1/archive',
      'https://api.example.com/api/v1/customers/customer%2F1/restore',
    ]);
  });

  it('encodes product list options and uses product mutation endpoints', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(
        jsonResponse(200, { items: [], product: { id: 'product-1' }, has_more: false }),
      ),
    );
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'web',
      fetchImplementation,
    });

    await client.listProducts({
      status: 'archived',
      sort: 'price_desc',
      search: 'A&B',
      limit: 50,
      cursor: 'next page',
    });
    await client.updateProduct('product/1', { selling_price: '25.50' });
    await client.archiveProduct('product/1');
    await client.restoreProduct('product/1');

    expect(fetchImplementation.mock.calls.map((call) => call[0])).toEqual([
      'https://api.example.com/api/v1/products?status=archived&sort=price_desc&search=A%26B&limit=50&cursor=next+page',
      'https://api.example.com/api/v1/products/product%2F1',
      'https://api.example.com/api/v1/products/product%2F1/archive',
      'https://api.example.com/api/v1/products/product%2F1/restore',
    ]);
  });

  it('encodes inventory queries and sends idempotency keys on stock mutations', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(jsonResponse(200, { items: [], movement: {}, stock: {} })),
    );
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'android',
      fetchImplementation,
    });

    await client.listStock({ search: 'A&B', limit: 25, cursor: 'next page' });
    await client.inventoryHistory({ productId: 'product/1', limit: 10 });
    await client.createStockReceipt(
      { product_id: 'product-1', quantity: '2.500', remarks: 'Received' },
      'submission-1',
    );

    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      'https://api.example.com/api/v1/inventory/stock?search=A%26B&limit=25&cursor=next+page',
    );
    expect(fetchImplementation.mock.calls[1]?.[0]).toBe(
      'https://api.example.com/api/v1/inventory/history?product_id=product%2F1&limit=10',
    );
    expect(fetchImplementation.mock.calls[2]?.[0]).toBe(
      'https://api.example.com/api/v1/inventory/stock-receipts',
    );
    const headers = fetchImplementation.mock.calls[2]?.[1]?.headers as Headers;
    expect(headers.get('Idempotency-Key')).toBe('submission-1');
  });

  it('encodes sales queries and sends idempotency keys on lifecycle mutations', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(jsonResponse(200, { items: [], sale: {}, has_more: false })),
    );
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'web',
      fetchImplementation,
    });

    await client.listSales({
      status: 'posted',
      sort: 'oldest',
      search: 'A&B',
      date: '2026-06-29',
      limit: 25,
      cursor: 'next page',
    });
    await client.searchSales('SALE-000001', { status: 'draft' });
    await client.createSale(
      { customer_id: 'customer-1', items: [{ product_id: 'product-1', quantity: '2', unit_price: '5' }] },
      'create-1',
    );
    await client.postSale('sale/1', 'post-1');
    await client.voidSale('sale/1', 'void-1');

    expect(fetchImplementation.mock.calls.map((call) => call[0])).toEqual([
      'https://api.example.com/api/v1/sales?status=posted&sort=oldest&search=A%26B&date=2026-06-29&limit=25&cursor=next+page',
      'https://api.example.com/api/v1/sales/search?status=draft&q=SALE-000001',
      'https://api.example.com/api/v1/sales',
      'https://api.example.com/api/v1/sales/sale%2F1/post',
      'https://api.example.com/api/v1/sales/sale%2F1/void',
    ]);
    expect(
      fetchImplementation.mock.calls.slice(2).map((call) =>
        (call[1]?.headers as Headers).get('Idempotency-Key'),
      ),
    ).toEqual(['create-1', 'post-1', 'void-1']);
  });

  it('encodes customer ledger filters without exposing tenant identifiers', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(jsonResponse(200, { items: [], has_more: false })),
    );
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'web',
      fetchImplementation,
    });

    await client.getCustomerFinancialSummary('customer/1');
    await client.listCustomerLedger('customer/1', {
      entryType: 'reversal',
      reference: 'SALE&1',
      date: '2026-06-29',
      limit: 25,
      cursor: 'next page',
    });
    await client.searchCustomerLedger('customer/1', 'SALE-000001', {
      entryType: 'sale',
    });

    expect(fetchImplementation.mock.calls.map((call) => call[0])).toEqual([
      'https://api.example.com/api/v1/customers/customer%2F1/financial-summary',
      'https://api.example.com/api/v1/customers/customer%2F1/ledger?entry_type=reversal&reference=SALE%261&date=2026-06-29&limit=25&cursor=next+page',
      'https://api.example.com/api/v1/customers/customer%2F1/ledger/search?entry_type=sale&q=SALE-000001',
    ]);
  });

  it('encodes payment queries and sends idempotency keys on payment mutations', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(jsonResponse(200, { items: [], payment: {}, has_more: false })),
    );
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'web',
      fetchImplementation,
    });

    await client.listPayments({
      status: 'posted',
      method: 'upi',
      sort: 'oldest',
      search: 'A&B',
      date: '2026-06-30',
      limit: 25,
      cursor: 'next page',
    });
    await client.searchPayments('PAY-000001', { status: 'void' });
    await client.listCustomerPayments('customer/1', { method: 'cash' });
    await client.getCustomerCredit('customer/1');
    await client.getCustomerBalance('customer/1');
    await client.createPayment(
      {
        customer_id: 'customer-1',
        payment_date: '2026-06-30',
        amount: '10',
        payment_method: 'cash',
      },
      'payment-create',
    );
    await client.voidPayment('payment/1', 'payment-void');

    expect(fetchImplementation.mock.calls.map((call) => call[0])).toEqual([
      'https://api.example.com/api/v1/payments?status=posted&method=upi&sort=oldest&search=A%26B&date=2026-06-30&limit=25&cursor=next+page',
      'https://api.example.com/api/v1/payments/search?status=void&q=PAY-000001',
      'https://api.example.com/api/v1/customers/customer%2F1/payments?method=cash',
      'https://api.example.com/api/v1/customers/customer%2F1/credit',
      'https://api.example.com/api/v1/customers/customer%2F1/balance',
      'https://api.example.com/api/v1/payments',
      'https://api.example.com/api/v1/payments/payment%2F1/void',
    ]);
    expect(
      fetchImplementation.mock.calls.slice(5).map((call) =>
        (call[1]?.headers as Headers).get('Idempotency-Key'),
      ),
    ).toEqual(['payment-create', 'payment-void']);
  });

  it('encodes invoice queries, lifecycle keys, and PDF downloads', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation(() =>
      Promise.resolve(jsonResponse(200, { items: [], invoice: {}, has_more: false })),
    );
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'web',
      fetchImplementation,
    });

    await client.listInvoices({
      status: 'issued',
      sort: 'oldest',
      search: 'A&B',
      date: '2026-06-30',
      limit: 25,
      cursor: 'next page',
    });
    await client.searchInvoices('INV-000001', { status: 'draft' });
    await client.listCustomerInvoices('customer/1', { status: 'void' });
    await client.createInvoice({ sale_id: 'sale-1' }, 'invoice-create');
    await client.issueInvoice('invoice/1', 'invoice-issue');
    await client.voidInvoice('invoice/1', 'invoice-void');
    await client.downloadInvoicePdf('invoice/1');

    expect(fetchImplementation.mock.calls.map((call) => call[0])).toEqual([
      'https://api.example.com/api/v1/invoices?status=issued&sort=oldest&search=A%26B&date=2026-06-30&limit=25&cursor=next+page',
      'https://api.example.com/api/v1/invoices/search?status=draft&q=INV-000001',
      'https://api.example.com/api/v1/customers/customer%2F1/invoices?status=void',
      'https://api.example.com/api/v1/invoices',
      'https://api.example.com/api/v1/invoices/invoice%2F1/issue',
      'https://api.example.com/api/v1/invoices/invoice%2F1/void',
      'https://api.example.com/api/v1/invoices/invoice%2F1/pdf',
    ]);
    expect(
      fetchImplementation.mock.calls.slice(3, 6).map((call) =>
        (call[1]?.headers as Headers).get('Idempotency-Key'),
      ),
    ).toEqual(['invoice-create', 'invoice-issue', 'invoice-void']);
    expect((fetchImplementation.mock.calls[6]?.[1]?.headers as Headers).get('Accept')).toBe(
      'application/pdf',
    );
  });

  it('encodes dashboard, global search, reports, and CSV exports without tenant identifiers', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockImplementation((url) => {
      const target = String(url);
      if (target.endsWith('.csv?search=A%26B&sort=alphabetical')) {
        return Promise.resolve(textResponse(200, '\uFEFFCustomer,Outstanding\n'));
      }
      if (target.includes('/reports/')) {
        return Promise.resolve(jsonResponse(200, { items: [], next_cursor: null }));
      }
      if (target.includes('/dashboard')) {
        return Promise.resolve(jsonResponse(200, { timezone: 'Asia/Kolkata' }));
      }
      return Promise.resolve(
        jsonResponse(200, {
          query: 'mango',
          customers: [],
          products: [],
          sales: [],
          invoices: [],
          payments: [],
          inventory: [],
        }),
      );
    });
    const client = new ApiClient({
      baseUrl: 'https://api.example.com/api/v1',
      platform: 'web',
      fetchImplementation,
    });

    await client.getDashboard();
    await client.globalSearch('mango & milk', { limitPerGroup: 5 });
    await client.salesReport({
      period: 'custom',
      dateFrom: '2026-06-01',
      dateTo: '2026-06-30',
      status: 'posted',
      search: 'A&B',
      sort: 'amount_desc',
      limit: 25,
      cursor: 'next page',
    });
    await client.paymentsReport({ status: 'void', sort: 'oldest' });
    await client.inventoryReport({ search: 'A&B', sort: 'value_desc' });
    const csv = await client.exportOutstandingCsv({ search: 'A&B', sort: 'alphabetical' });

    expect(fetchImplementation.mock.calls.map((call) => call[0])).toEqual([
      'https://api.example.com/api/v1/dashboard',
      'https://api.example.com/api/v1/search?q=mango+%26+milk&limit_per_group=5',
      'https://api.example.com/api/v1/reports/sales?period=custom&date_from=2026-06-01&date_to=2026-06-30&status=posted&search=A%26B&sort=amount_desc&limit=25&cursor=next+page',
      'https://api.example.com/api/v1/reports/payments?status=void&sort=oldest',
      'https://api.example.com/api/v1/reports/inventory?search=A%26B&sort=value_desc',
      'https://api.example.com/api/v1/reports/outstanding.csv?search=A%26B&sort=alphabetical',
    ]);
    expect((fetchImplementation.mock.calls[5]?.[1]?.headers as Headers).get('Accept')).toBe(
      'text/csv',
    );
    expect(csv).toContain('Customer,Outstanding');
  });
});
