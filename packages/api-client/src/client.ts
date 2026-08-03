import type { components } from './schema';

export type SignupRequest = components['schemas']['SignupRequest'];
export type LoginRequest = components['schemas']['LoginRequest'];
export type ForgotPasswordRequest = components['schemas']['ForgotPasswordRequest'];
export type ResetPasswordRequest = components['schemas']['ResetPasswordRequest'];
export type ChangePasswordRequest = components['schemas']['ChangePasswordRequest'];
export type MessageResponse = components['schemas']['MessageResponse'];
export type AuthResponse = components['schemas']['AuthResponse'];
export type MeResponse = components['schemas']['MeResponse'];
export type LogoutResponse = components['schemas']['LogoutResponse'];
export type User = components['schemas']['UserResponse'];
export type BusinessSettings = components['schemas']['BusinessSettingsResponse'];
export type BusinessSettingsUpdateRequest =
  components['schemas']['BusinessSettingsUpdateRequest'];
export type CurrencyCode = BusinessSettings['currency'];
export type LanguageCode = BusinessSettings['language'];
export type ThemePreference = BusinessSettings['theme'];
export type Customer = components['schemas']['CustomerResponse'];
export type CustomerCreateRequest = components['schemas']['CustomerCreateRequest'];
export type CustomerUpdateRequest = components['schemas']['CustomerUpdateRequest'];
export type CustomerListResponse = components['schemas']['CustomerListResponse'];
export type CustomerMutationResponse = components['schemas']['CustomerMutationResponse'];

export type CustomerStatus = 'all' | 'active' | 'archived';
export type CustomerSort = 'newest' | 'oldest' | 'name_asc' | 'name_desc';

export interface CustomerListOptions {
  status?: CustomerStatus;
  sort?: CustomerSort;
  search?: string;
  limit?: number;
  cursor?: string;
}

export type Product = components['schemas']['ProductResponse'];
export type ProductCreateRequest = components['schemas']['ProductCreateRequest'];
export type ProductUpdateRequest = components['schemas']['ProductUpdateRequest'];
export type ProductListResponse = components['schemas']['ProductListResponse'];
export type ProductMutationResponse = components['schemas']['ProductMutationResponse'];
export type ProductStatus = 'all' | 'active' | 'archived';
export type ProductSort =
  | 'newest'
  | 'oldest'
  | 'name_asc'
  | 'name_desc'
  | 'price_asc'
  | 'price_desc';
export type ProductUnit =
  | 'piece'
  | 'kg'
  | 'gram'
  | 'litre'
  | 'millilitre'
  | 'box'
  | 'packet'
  | 'dozen';

export interface ProductListOptions {
  status?: ProductStatus;
  sort?: ProductSort;
  search?: string;
  limit?: number;
  cursor?: string;
}

export type PositiveStockRequest = components['schemas']['PositiveStockRequest'];
export type AdjustmentRequest = components['schemas']['AdjustmentRequest'];
export type InventoryMutationResponse = components['schemas']['InventoryMutationResponse'];
export type StockItem = components['schemas']['StockItemResponse'];
export type StockListResponse = components['schemas']['StockListResponse'];
export type StockMovement = components['schemas']['StockMovementResponse'];
export type MovementHistoryResponse = components['schemas']['MovementHistoryResponse'];
export type Warehouse = components['schemas']['WarehouseResponse'];
export type MovementType = StockMovement['movement_type'];
export type LowStockStatus = StockItem['low_stock_status'];

export interface StockListOptions {
  warehouseId?: string;
  search?: string;
  limit?: number;
  cursor?: string;
}

export interface MovementHistoryOptions extends StockListOptions {
  productId?: string;
}

export type Sale = components['schemas']['SaleResponse'];
export type SaleItem = components['schemas']['SaleItemResponse'];
export type SaleListItem = components['schemas']['SaleListItemResponse'];
export type SaleCreateRequest = components['schemas']['SaleCreateRequest'];
export type SaleUpdateRequest = components['schemas']['SaleUpdateRequest'];
export type SaleListResponse = components['schemas']['SaleListResponse'];
export type SaleMutationResponse = components['schemas']['SaleMutationResponse'];
export type SaleStatus = 'all' | 'draft' | 'posted' | 'void';
export type SaleSort = 'newest' | 'oldest';

export interface SaleListOptions {
  status?: SaleStatus;
  sort?: SaleSort;
  search?: string;
  date?: string;
  limit?: number;
  cursor?: string;
}

export type CustomerFinancialSummary =
  components['schemas']['CustomerFinancialSummaryResponse'];
export type LedgerEntry = components['schemas']['LedgerEntryResponse'];
export type LedgerListResponse = components['schemas']['LedgerListResponse'];
export type LedgerEntryType = 'all' | 'sale' | 'reversal' | 'payment' | 'payment_reversal';

export interface LedgerListOptions {
  entryType?: LedgerEntryType;
  reference?: string;
  date?: string;
  limit?: number;
  cursor?: string;
}

export type Payment = components['schemas']['PaymentResponse'];
export type PaymentListItem = components['schemas']['PaymentListItemResponse'];
export type PaymentCreateRequest = components['schemas']['PaymentCreateRequest'];
export type PaymentMutationResponse = components['schemas']['PaymentMutationResponse'];
export type PaymentListResponse = components['schemas']['PaymentListResponse'];
export type CustomerCredit = components['schemas']['CustomerCreditResponse'];
export type CustomerBalance = components['schemas']['CustomerBalanceResponse'];
export type PaymentStatus = 'all' | 'posted' | 'void';
export type PaymentMethod = 'all' | 'cash' | 'upi' | 'bank_transfer' | 'cheque' | 'other';
export type PaymentSort = 'newest' | 'oldest';

export interface PaymentListOptions {
  status?: PaymentStatus;
  method?: PaymentMethod;
  sort?: PaymentSort;
  search?: string;
  date?: string;
  limit?: number;
  cursor?: string;
}

export type Invoice = components['schemas']['InvoiceResponse'];
export type InvoiceItem = components['schemas']['InvoiceItemResponse'];
export type InvoiceCreateRequest = components['schemas']['InvoiceCreateRequest'];
export type InvoiceListItem = components['schemas']['InvoiceListItemResponse'];
export type InvoiceListResponse = components['schemas']['InvoiceListResponse'];
export type InvoiceMutationResponse = components['schemas']['InvoiceMutationResponse'];
export type InvoiceStatus = 'all' | 'draft' | 'issued' | 'void';
export type InvoiceSort = 'newest' | 'oldest';

export interface InvoiceListOptions {
  status?: InvoiceStatus;
  sort?: InvoiceSort;
  search?: string;
  date?: string;
  limit?: number;
  cursor?: string;
}

export type Dashboard = components['schemas']['DashboardResponse'];
export type DashboardMetric = components['schemas']['DashboardMetricResponse'];
export type RecentActivityItem = components['schemas']['RecentActivityItemResponse'];
export type RecentInventoryActivity =
  components['schemas']['RecentInventoryActivityResponse'];
export type TopSellingProduct = components['schemas']['TopSellingProductResponse'];
export type OutstandingCustomer = components['schemas']['OutstandingCustomerResponse'];
export type GlobalSearchResult = components['schemas']['GlobalSearchResponse'];
export type GlobalSearchItem = components['schemas']['GlobalSearchItemResponse'];
export type SalesReport = components['schemas']['SalesReportResponse'];
export type SalesReportRow = components['schemas']['SalesReportRowResponse'];
export type PaymentReport = components['schemas']['PaymentReportResponse'];
export type PaymentReportRow = components['schemas']['PaymentReportRowResponse'];
export type OutstandingReport = components['schemas']['OutstandingReportResponse'];
export type OutstandingReportRow = components['schemas']['OutstandingReportRowResponse'];
export type InventoryReport = components['schemas']['InventoryReportResponse'];
export type InventoryReportRow = components['schemas']['InventoryReportRowResponse'];
export type LowStockReport = components['schemas']['LowStockReportResponse'];
export type ReportPeriod = 'today' | 'yesterday' | 'this_week' | 'this_month' | 'custom' | 'all';
export type ReportStatus = 'all' | 'draft' | 'posted' | 'void' | 'issued';
export type SalesReportSort =
  | 'newest'
  | 'oldest'
  | 'amount_desc'
  | 'amount_asc'
  | 'customer_asc'
  | 'customer_desc';
export type PaymentReportSort = SalesReportSort;
export type OutstandingReportSort = 'highest_outstanding' | 'alphabetical';
export type InventoryReportSort =
  | 'name_asc'
  | 'name_desc'
  | 'stock_asc'
  | 'stock_desc'
  | 'value_asc'
  | 'value_desc';
export type LowStockReportSort = 'lowest_stock' | 'alphabetical';

export interface DatedReportOptions {
  period?: ReportPeriod;
  dateFrom?: string;
  dateTo?: string;
  status?: ReportStatus;
  search?: string;
  sort?: SalesReportSort | PaymentReportSort;
  limit?: number;
  cursor?: string;
}

export interface OutstandingReportOptions {
  search?: string;
  sort?: OutstandingReportSort;
  limit?: number;
  cursor?: string;
}

export interface InventoryReportOptions {
  search?: string;
  sort?: InventoryReportSort;
  limit?: number;
  cursor?: string;
}

export interface LowStockReportOptions {
  search?: string;
  sort?: LowStockReportSort;
  limit?: number;
  cursor?: string;
}

export function createIdempotencyKey(): string {
  const random = Math.random().toString(36).slice(2);
  return `${Date.now().toString(36)}-${random}-${Math.random().toString(36).slice(2)}`;
}

type FieldErrors = Record<string, string>;

interface ErrorBody {
  error?: {
    code?: string;
    message?: string;
    request_id?: string | null;
    field_errors?: FieldErrors;
  };
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly fieldErrors: FieldErrors = {},
    public readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export interface ApiClientOptions {
  baseUrl: string;
  platform: 'android' | 'ios' | 'web' | string;
  fetchImplementation?: typeof fetch;
  startupRetryDelaysMs?: readonly number[];
}

type UnauthorizedHandler = () => Promise<string | null>;

export class ApiClient {
  private accessToken: string | null = null;
  private unauthorizedHandler: UnauthorizedHandler | null = null;
  private refreshInFlight: Promise<string | null> | null = null;
  private readonly baseUrl: string;
  private readonly platform: string;
  private readonly fetchImplementation: typeof fetch;
  private readonly startupRetryDelaysMs: readonly number[];

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, '');
    this.platform = options.platform;
    this.fetchImplementation = (options.fetchImplementation ?? fetch).bind(globalThis);
    this.startupRetryDelaysMs = options.startupRetryDelaysMs ?? [400, 1200];
  }

  setAccessToken(token: string | null): void {
    this.accessToken = token;
  }

  setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
    this.unauthorizedHandler = handler;
  }

  signup(payload: SignupRequest): Promise<AuthResponse> {
    return this.request<AuthResponse>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, false);
  }

  login(payload: LoginRequest): Promise<AuthResponse> {
    return this.request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, false);
  }

  forgotPassword(payload: ForgotPasswordRequest): Promise<MessageResponse> {
    return this.request<MessageResponse>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, false);
  }

  resetPassword(payload: ResetPasswordRequest): Promise<MessageResponse> {
    return this.request<MessageResponse>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, false);
  }

  changePassword(payload: ChangePasswordRequest): Promise<MessageResponse> {
    return this.request<MessageResponse>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, true);
  }

  refresh(refreshToken: string | null): Promise<AuthResponse> {
    return this.request<AuthResponse>('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    }, false);
  }

  me(): Promise<MeResponse> {
    return this.request<MeResponse>('/auth/me', { method: 'GET' }, true);
  }

  getBusinessSettings(signal?: AbortSignal): Promise<BusinessSettings> {
    return this.request<BusinessSettings>('/business/settings', { method: 'GET', signal }, true);
  }

  updateBusinessSettings(
    payload: BusinessSettingsUpdateRequest,
  ): Promise<BusinessSettings> {
    return this.request<BusinessSettings>('/business/settings', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }, true);
  }

  logout(): Promise<LogoutResponse> {
    return this.request<LogoutResponse>('/auth/logout', { method: 'POST' }, true);
  }

  createCustomer(payload: CustomerCreateRequest): Promise<CustomerMutationResponse> {
    return this.request<CustomerMutationResponse>('/customers', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, true);
  }

  getCustomer(customerId: string, signal?: AbortSignal): Promise<Customer> {
    return this.request<Customer>(`/customers/${encodeURIComponent(customerId)}`, {
      method: 'GET',
      signal,
    }, true);
  }

  getCustomerByCode(customerCode: string, signal?: AbortSignal): Promise<Customer> {
    return this.request<Customer>(`/customers/code/${encodeURIComponent(customerCode)}`, {
      method: 'GET',
      signal,
    }, true);
  }

  updateCustomer(
    customerId: string,
    payload: CustomerUpdateRequest,
  ): Promise<CustomerMutationResponse> {
    return this.request<CustomerMutationResponse>(
      `/customers/${encodeURIComponent(customerId)}`,
      { method: 'PATCH', body: JSON.stringify(payload) },
      true,
    );
  }

  archiveCustomer(customerId: string): Promise<CustomerMutationResponse> {
    return this.customerStateAction(customerId, 'archive');
  }

  restoreCustomer(customerId: string): Promise<CustomerMutationResponse> {
    return this.customerStateAction(customerId, 'restore');
  }

  listCustomers(
    options: CustomerListOptions = {},
    signal?: AbortSignal,
  ): Promise<CustomerListResponse> {
    const query = new URLSearchParams();
    if (options.status) query.set('status', options.status);
    if (options.sort) query.set('sort', options.sort);
    if (options.search) query.set('search', options.search);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    const suffix = query.size ? `?${query.toString()}` : '';
    return this.request<CustomerListResponse>(`/customers${suffix}`, {
      method: 'GET',
      signal,
    }, true);
  }

  searchCustomers(
    queryText: string,
    options: Omit<CustomerListOptions, 'search'> = {},
    signal?: AbortSignal,
  ): Promise<CustomerListResponse> {
    const query = new URLSearchParams({ q: queryText });
    if (options.status) query.set('status', options.status);
    if (options.sort) query.set('sort', options.sort);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    return this.request<CustomerListResponse>(`/customers/search?${query.toString()}`, {
      method: 'GET',
      signal,
    }, true);
  }

  createProduct(payload: ProductCreateRequest): Promise<ProductMutationResponse> {
    return this.request<ProductMutationResponse>('/products', {
      method: 'POST',
      body: JSON.stringify(payload),
    }, true);
  }

  getProduct(productId: string, signal?: AbortSignal): Promise<Product> {
    return this.request<Product>(`/products/${encodeURIComponent(productId)}`, {
      method: 'GET',
      signal,
    }, true);
  }

  getProductByCode(productCode: string, signal?: AbortSignal): Promise<Product> {
    return this.request<Product>(`/products/code/${encodeURIComponent(productCode)}`, {
      method: 'GET',
      signal,
    }, true);
  }

  updateProduct(
    productId: string,
    payload: ProductUpdateRequest,
  ): Promise<ProductMutationResponse> {
    return this.request<ProductMutationResponse>(
      `/products/${encodeURIComponent(productId)}`,
      { method: 'PATCH', body: JSON.stringify(payload) },
      true,
    );
  }

  archiveProduct(productId: string): Promise<ProductMutationResponse> {
    return this.productStateAction(productId, 'archive');
  }

  restoreProduct(productId: string): Promise<ProductMutationResponse> {
    return this.productStateAction(productId, 'restore');
  }

  listProducts(
    options: ProductListOptions = {},
    signal?: AbortSignal,
  ): Promise<ProductListResponse> {
    const query = new URLSearchParams();
    if (options.status) query.set('status', options.status);
    if (options.sort) query.set('sort', options.sort);
    if (options.search) query.set('search', options.search);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    const suffix = query.size ? `?${query.toString()}` : '';
    return this.request<ProductListResponse>(`/products${suffix}`, {
      method: 'GET',
      signal,
    }, true);
  }

  searchProducts(
    queryText: string,
    options: Omit<ProductListOptions, 'search'> = {},
    signal?: AbortSignal,
  ): Promise<ProductListResponse> {
    const query = new URLSearchParams({ q: queryText });
    if (options.status) query.set('status', options.status);
    if (options.sort) query.set('sort', options.sort);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    return this.request<ProductListResponse>(`/products/search?${query.toString()}`, {
      method: 'GET',
      signal,
    }, true);
  }

  getDefaultWarehouse(signal?: AbortSignal): Promise<Warehouse> {
    return this.request<Warehouse>('/inventory/warehouses/default', {
      method: 'GET',
      signal,
    }, true);
  }

  listStock(
    options: StockListOptions = {},
    signal?: AbortSignal,
  ): Promise<StockListResponse> {
    const query = new URLSearchParams();
    if (options.warehouseId) query.set('warehouse_id', options.warehouseId);
    if (options.search) query.set('search', options.search);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    const suffix = query.size ? `?${query.toString()}` : '';
    return this.request<StockListResponse>(`/inventory/stock${suffix}`, {
      method: 'GET',
      signal,
    }, true);
  }

  getCurrentStock(
    productId: string,
    warehouseId?: string,
    signal?: AbortSignal,
  ): Promise<StockItem> {
    const query = new URLSearchParams();
    if (warehouseId) query.set('warehouse_id', warehouseId);
    const suffix = query.size ? `?${query.toString()}` : '';
    return this.request<StockItem>(
      `/inventory/stock/${encodeURIComponent(productId)}${suffix}`,
      { method: 'GET', signal },
      true,
    );
  }

  inventoryHistory(
    options: MovementHistoryOptions = {},
    signal?: AbortSignal,
  ): Promise<MovementHistoryResponse> {
    const query = new URLSearchParams();
    if (options.warehouseId) query.set('warehouse_id', options.warehouseId);
    if (options.productId) query.set('product_id', options.productId);
    if (options.search) query.set('search', options.search);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    const suffix = query.size ? `?${query.toString()}` : '';
    return this.request<MovementHistoryResponse>(`/inventory/history${suffix}`, {
      method: 'GET',
      signal,
    }, true);
  }

  createOpeningStock(
    payload: PositiveStockRequest,
    idempotencyKey: string,
  ): Promise<InventoryMutationResponse> {
    return this.postInventory('opening-stock', payload, idempotencyKey);
  }

  createStockReceipt(
    payload: PositiveStockRequest,
    idempotencyKey: string,
  ): Promise<InventoryMutationResponse> {
    return this.postInventory('stock-receipts', payload, idempotencyKey);
  }

  createCustomerReturn(
    payload: PositiveStockRequest,
    idempotencyKey: string,
  ): Promise<InventoryMutationResponse> {
    return this.postInventory('customer-returns', payload, idempotencyKey);
  }

  createDamageEntry(
    payload: PositiveStockRequest,
    idempotencyKey: string,
  ): Promise<InventoryMutationResponse> {
    return this.postInventory('damage', payload, idempotencyKey);
  }

  createSpoilageEntry(
    payload: PositiveStockRequest,
    idempotencyKey: string,
  ): Promise<InventoryMutationResponse> {
    return this.postInventory('spoilage', payload, idempotencyKey);
  }

  createStockAdjustment(
    payload: AdjustmentRequest,
    idempotencyKey: string,
  ): Promise<InventoryMutationResponse> {
    return this.postInventory('adjustments', payload, idempotencyKey);
  }

  createSale(
    payload: SaleCreateRequest,
    idempotencyKey: string,
  ): Promise<SaleMutationResponse> {
    return this.request<SaleMutationResponse>('/sales', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload),
    }, true);
  }

  getSale(saleId: string, signal?: AbortSignal): Promise<Sale> {
    return this.request<Sale>(`/sales/${encodeURIComponent(saleId)}`, {
      method: 'GET',
      signal,
    }, true);
  }

  getSaleByNumber(saleNumber: string, signal?: AbortSignal): Promise<Sale> {
    return this.request<Sale>(`/sales/number/${encodeURIComponent(saleNumber)}`, {
      method: 'GET',
      signal,
    }, true);
  }

  updateSale(saleId: string, payload: SaleUpdateRequest): Promise<SaleMutationResponse> {
    return this.request<SaleMutationResponse>(`/sales/${encodeURIComponent(saleId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }, true);
  }

  postSale(saleId: string, idempotencyKey: string): Promise<SaleMutationResponse> {
    return this.saleStateAction(saleId, 'post', idempotencyKey);
  }

  voidSale(saleId: string, idempotencyKey: string): Promise<SaleMutationResponse> {
    return this.saleStateAction(saleId, 'void', idempotencyKey);
  }

  listSales(options: SaleListOptions = {}, signal?: AbortSignal): Promise<SaleListResponse> {
    const query = this.saleListQuery(options);
    const suffix = query.size ? `?${query.toString()}` : '';
    return this.request<SaleListResponse>(`/sales${suffix}`, {
      method: 'GET',
      signal,
    }, true);
  }

  searchSales(
    queryText: string,
    options: Omit<SaleListOptions, 'search'> = {},
    signal?: AbortSignal,
  ): Promise<SaleListResponse> {
    const query = this.saleListQuery(options);
    if (queryText) query.set('q', queryText);
    return this.request<SaleListResponse>(`/sales/search?${query.toString()}`, {
      method: 'GET',
      signal,
    }, true);
  }

  getCustomerFinancialSummary(
    customerId: string,
    signal?: AbortSignal,
  ): Promise<CustomerFinancialSummary> {
    return this.request<CustomerFinancialSummary>(
      `/customers/${encodeURIComponent(customerId)}/financial-summary`,
      { method: 'GET', signal },
      true,
    );
  }

  listCustomerLedger(
    customerId: string,
    options: LedgerListOptions = {},
    signal?: AbortSignal,
  ): Promise<LedgerListResponse> {
    const query = this.ledgerListQuery(options);
    const suffix = query.size ? `?${query.toString()}` : '';
    return this.request<LedgerListResponse>(
      `/customers/${encodeURIComponent(customerId)}/ledger${suffix}`,
      { method: 'GET', signal },
      true,
    );
  }

  searchCustomerLedger(
    customerId: string,
    queryText: string,
    options: Omit<LedgerListOptions, 'reference'> = {},
    signal?: AbortSignal,
  ): Promise<LedgerListResponse> {
    const query = this.ledgerListQuery(options);
    if (queryText) query.set('q', queryText);
    return this.request<LedgerListResponse>(
      `/customers/${encodeURIComponent(customerId)}/ledger/search?${query.toString()}`,
      { method: 'GET', signal },
      true,
    );
  }

  createPayment(
    payload: PaymentCreateRequest,
    idempotencyKey: string,
  ): Promise<PaymentMutationResponse> {
    return this.request<PaymentMutationResponse>('/payments', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload),
    }, true);
  }

  getPayment(paymentId: string, signal?: AbortSignal): Promise<Payment> {
    return this.request<Payment>(`/payments/${encodeURIComponent(paymentId)}`, {
      method: 'GET',
      signal,
    }, true);
  }

  getPaymentByNumber(paymentNumber: string, signal?: AbortSignal): Promise<Payment> {
    return this.request<Payment>(`/payments/number/${encodeURIComponent(paymentNumber)}`, {
      method: 'GET',
      signal,
    }, true);
  }

  voidPayment(paymentId: string, idempotencyKey: string): Promise<PaymentMutationResponse> {
    return this.request<PaymentMutationResponse>(
      `/payments/${encodeURIComponent(paymentId)}/void`,
      { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey } },
      true,
    );
  }

  listPayments(
    options: PaymentListOptions = {},
    signal?: AbortSignal,
  ): Promise<PaymentListResponse> {
    const query = this.paymentListQuery(options);
    const suffix = query.size ? `?${query.toString()}` : '';
    return this.request<PaymentListResponse>(`/payments${suffix}`, {
      method: 'GET',
      signal,
    }, true);
  }

  searchPayments(
    queryText: string,
    options: Omit<PaymentListOptions, 'search'> = {},
    signal?: AbortSignal,
  ): Promise<PaymentListResponse> {
    const query = this.paymentListQuery(options);
    if (queryText) query.set('q', queryText);
    return this.request<PaymentListResponse>(`/payments/search?${query.toString()}`, {
      method: 'GET',
      signal,
    }, true);
  }

  listCustomerPayments(
    customerId: string,
    options: PaymentListOptions = {},
    signal?: AbortSignal,
  ): Promise<PaymentListResponse> {
    const query = this.paymentListQuery(options);
    const suffix = query.size ? `?${query.toString()}` : '';
    return this.request<PaymentListResponse>(
      `/customers/${encodeURIComponent(customerId)}/payments${suffix}`,
      { method: 'GET', signal },
      true,
    );
  }

  getCustomerCredit(customerId: string, signal?: AbortSignal): Promise<CustomerCredit> {
    return this.request<CustomerCredit>(
      `/customers/${encodeURIComponent(customerId)}/credit`,
      { method: 'GET', signal },
      true,
    );
  }

  getCustomerBalance(customerId: string, signal?: AbortSignal): Promise<CustomerBalance> {
    return this.request<CustomerBalance>(
      `/customers/${encodeURIComponent(customerId)}/balance`,
      { method: 'GET', signal },
      true,
    );
  }

  createInvoice(
    payload: InvoiceCreateRequest,
    idempotencyKey: string,
  ): Promise<InvoiceMutationResponse> {
    return this.request<InvoiceMutationResponse>('/invoices', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload),
    }, true);
  }

  getInvoice(invoiceId: string, signal?: AbortSignal): Promise<Invoice> {
    return this.request<Invoice>(`/invoices/${encodeURIComponent(invoiceId)}`, {
      method: 'GET',
      signal,
    }, true);
  }

  getInvoiceByNumber(invoiceNumber: string, signal?: AbortSignal): Promise<Invoice> {
    return this.request<Invoice>(`/invoices/number/${encodeURIComponent(invoiceNumber)}`, {
      method: 'GET',
      signal,
    }, true);
  }

  issueInvoice(invoiceId: string, idempotencyKey: string): Promise<InvoiceMutationResponse> {
    return this.invoiceStateAction(invoiceId, 'issue', idempotencyKey);
  }

  voidInvoice(invoiceId: string, idempotencyKey: string): Promise<InvoiceMutationResponse> {
    return this.invoiceStateAction(invoiceId, 'void', idempotencyKey);
  }

  listInvoices(
    options: InvoiceListOptions = {},
    signal?: AbortSignal,
  ): Promise<InvoiceListResponse> {
    const query = this.invoiceListQuery(options);
    const suffix = query.size ? `?${query.toString()}` : '';
    return this.request<InvoiceListResponse>(`/invoices${suffix}`, {
      method: 'GET',
      signal,
    }, true);
  }

  searchInvoices(
    queryText: string,
    options: Omit<InvoiceListOptions, 'search'> = {},
    signal?: AbortSignal,
  ): Promise<InvoiceListResponse> {
    const query = this.invoiceListQuery(options);
    if (queryText) query.set('q', queryText);
    return this.request<InvoiceListResponse>(`/invoices/search?${query.toString()}`, {
      method: 'GET',
      signal,
    }, true);
  }

  listCustomerInvoices(
    customerId: string,
    options: InvoiceListOptions = {},
    signal?: AbortSignal,
  ): Promise<InvoiceListResponse> {
    const query = this.invoiceListQuery(options);
    const suffix = query.size ? `?${query.toString()}` : '';
    return this.request<InvoiceListResponse>(
      `/customers/${encodeURIComponent(customerId)}/invoices${suffix}`,
      { method: 'GET', signal },
      true,
    );
  }

  downloadInvoicePdf(invoiceId: string, signal?: AbortSignal): Promise<ArrayBuffer> {
    return this.requestArrayBuffer(
      `/invoices/${encodeURIComponent(invoiceId)}/pdf`,
      { method: 'GET', signal, headers: { Accept: 'application/pdf' } },
      true,
    );
  }

  getDashboard(signal?: AbortSignal): Promise<Dashboard> {
    return this.request<Dashboard>('/dashboard', { method: 'GET', signal }, true);
  }

  globalSearch(
    queryText: string,
    options: { limitPerGroup?: number } = {},
    signal?: AbortSignal,
  ): Promise<GlobalSearchResult> {
    const query = new URLSearchParams({ q: queryText });
    if (options.limitPerGroup) query.set('limit_per_group', String(options.limitPerGroup));
    return this.request<GlobalSearchResult>(`/search?${query.toString()}`, {
      method: 'GET',
      signal,
    }, true);
  }

  salesReport(options: DatedReportOptions = {}, signal?: AbortSignal): Promise<SalesReport> {
    const query = this.datedReportQuery(options);
    return this.request<SalesReport>(this.withQuery('/reports/sales', query), {
      method: 'GET',
      signal,
    }, true);
  }

  paymentsReport(
    options: DatedReportOptions = {},
    signal?: AbortSignal,
  ): Promise<PaymentReport> {
    const query = this.datedReportQuery(options);
    return this.request<PaymentReport>(this.withQuery('/reports/payments', query), {
      method: 'GET',
      signal,
    }, true);
  }

  outstandingReport(
    options: OutstandingReportOptions = {},
    signal?: AbortSignal,
  ): Promise<OutstandingReport> {
    const query = this.outstandingReportQuery(options);
    return this.request<OutstandingReport>(this.withQuery('/reports/outstanding', query), {
      method: 'GET',
      signal,
    }, true);
  }

  inventoryReport(
    options: InventoryReportOptions = {},
    signal?: AbortSignal,
  ): Promise<InventoryReport> {
    const query = this.inventoryReportQuery(options);
    return this.request<InventoryReport>(this.withQuery('/reports/inventory', query), {
      method: 'GET',
      signal,
    }, true);
  }

  lowStockReport(
    options: LowStockReportOptions = {},
    signal?: AbortSignal,
  ): Promise<LowStockReport> {
    const query = this.lowStockReportQuery(options);
    return this.request<LowStockReport>(this.withQuery('/reports/low-stock', query), {
      method: 'GET',
      signal,
    }, true);
  }

  exportSalesCsv(options: DatedReportOptions = {}, signal?: AbortSignal): Promise<string> {
    const query = this.datedReportQuery(options);
    return this.requestText(this.withQuery('/reports/sales.csv', query), {
      method: 'GET',
      signal,
      headers: { Accept: 'text/csv' },
    }, true);
  }

  exportPaymentsCsv(options: DatedReportOptions = {}, signal?: AbortSignal): Promise<string> {
    const query = this.datedReportQuery(options);
    return this.requestText(this.withQuery('/reports/payments.csv', query), {
      method: 'GET',
      signal,
      headers: { Accept: 'text/csv' },
    }, true);
  }

  exportOutstandingCsv(
    options: OutstandingReportOptions = {},
    signal?: AbortSignal,
  ): Promise<string> {
    const query = this.outstandingReportQuery(options);
    return this.requestText(this.withQuery('/reports/outstanding.csv', query), {
      method: 'GET',
      signal,
      headers: { Accept: 'text/csv' },
    }, true);
  }

  exportInventoryCsv(options: InventoryReportOptions = {}, signal?: AbortSignal): Promise<string> {
    const query = this.inventoryReportQuery(options);
    return this.requestText(this.withQuery('/reports/inventory.csv', query), {
      method: 'GET',
      signal,
      headers: { Accept: 'text/csv' },
    }, true);
  }

  exportLowStockCsv(options: LowStockReportOptions = {}, signal?: AbortSignal): Promise<string> {
    const query = this.lowStockReportQuery(options);
    return this.requestText(this.withQuery('/reports/low-stock.csv', query), {
      method: 'GET',
      signal,
      headers: { Accept: 'text/csv' },
    }, true);
  }

  private postInventory(
    path: string,
    payload: PositiveStockRequest | AdjustmentRequest,
    idempotencyKey: string,
  ): Promise<InventoryMutationResponse> {
    return this.request<InventoryMutationResponse>(`/inventory/${path}`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload),
    }, true);
  }

  private saleListQuery(options: SaleListOptions): URLSearchParams {
    const query = new URLSearchParams();
    if (options.status) query.set('status', options.status);
    if (options.sort) query.set('sort', options.sort);
    if (options.search) query.set('search', options.search);
    if (options.date) query.set('date', options.date);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    return query;
  }

  private ledgerListQuery(options: LedgerListOptions): URLSearchParams {
    const query = new URLSearchParams();
    if (options.entryType) query.set('entry_type', options.entryType);
    if (options.reference) query.set('reference', options.reference);
    if (options.date) query.set('date', options.date);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    return query;
  }

  private paymentListQuery(options: PaymentListOptions): URLSearchParams {
    const query = new URLSearchParams();
    if (options.status) query.set('status', options.status);
    if (options.method) query.set('method', options.method);
    if (options.sort) query.set('sort', options.sort);
    if (options.search) query.set('search', options.search);
    if (options.date) query.set('date', options.date);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    return query;
  }

  private invoiceListQuery(options: InvoiceListOptions): URLSearchParams {
    const query = new URLSearchParams();
    if (options.status) query.set('status', options.status);
    if (options.sort) query.set('sort', options.sort);
    if (options.search) query.set('search', options.search);
    if (options.date) query.set('date', options.date);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    return query;
  }

  private datedReportQuery(options: DatedReportOptions): URLSearchParams {
    const query = new URLSearchParams();
    if (options.period) query.set('period', options.period);
    if (options.dateFrom) query.set('date_from', options.dateFrom);
    if (options.dateTo) query.set('date_to', options.dateTo);
    if (options.status) query.set('status', options.status);
    if (options.search) query.set('search', options.search);
    if (options.sort) query.set('sort', options.sort);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    return query;
  }

  private outstandingReportQuery(options: OutstandingReportOptions): URLSearchParams {
    const query = new URLSearchParams();
    if (options.search) query.set('search', options.search);
    if (options.sort) query.set('sort', options.sort);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    return query;
  }

  private inventoryReportQuery(options: InventoryReportOptions): URLSearchParams {
    const query = new URLSearchParams();
    if (options.search) query.set('search', options.search);
    if (options.sort) query.set('sort', options.sort);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    return query;
  }

  private lowStockReportQuery(options: LowStockReportOptions): URLSearchParams {
    const query = new URLSearchParams();
    if (options.search) query.set('search', options.search);
    if (options.sort) query.set('sort', options.sort);
    if (options.limit) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    return query;
  }

  private withQuery(path: string, query: URLSearchParams): string {
    const serialized = query.toString();
    return serialized ? `${path}?${serialized}` : path;
  }

  private invoiceStateAction(
    invoiceId: string,
    action: 'issue' | 'void',
    idempotencyKey: string,
  ): Promise<InvoiceMutationResponse> {
    return this.request<InvoiceMutationResponse>(
      `/invoices/${encodeURIComponent(invoiceId)}/${action}`,
      { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey } },
      true,
    );
  }

  private saleStateAction(
    saleId: string,
    action: 'post' | 'void',
    idempotencyKey: string,
  ): Promise<SaleMutationResponse> {
    return this.request<SaleMutationResponse>(
      `/sales/${encodeURIComponent(saleId)}/${action}`,
      { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey } },
      true,
    );
  }

  private productStateAction(
    productId: string,
    action: 'archive' | 'restore',
  ): Promise<ProductMutationResponse> {
    return this.request<ProductMutationResponse>(
      `/products/${encodeURIComponent(productId)}/${action}`,
      { method: 'POST' },
      true,
    );
  }

  private customerStateAction(
    customerId: string,
    action: 'archive' | 'restore',
  ): Promise<CustomerMutationResponse> {
    return this.request<CustomerMutationResponse>(
      `/customers/${encodeURIComponent(customerId)}/${action}`,
      { method: 'POST' },
      true,
    );
  }

  private async request<T>(
    path: string,
    init: RequestInit,
    retryAfterUnauthorized: boolean,
  ): Promise<T> {
    const response = await this.fetchResponse(path, init);

    if (response.status === 401 && retryAfterUnauthorized && this.unauthorizedHandler) {
      const refreshedToken = await this.refreshAccessToken();
      if (refreshedToken) {
        this.accessToken = refreshedToken;
        return this.request<T>(path, init, false);
      }
    }

    if (!response.ok) {
      throw await this.toApiError(response);
    }

    return (await response.json()) as T;
  }

  private async requestArrayBuffer(
    path: string,
    init: RequestInit,
    retryAfterUnauthorized: boolean,
  ): Promise<ArrayBuffer> {
    const response = await this.fetchResponse(path, init);

    if (response.status === 401 && retryAfterUnauthorized && this.unauthorizedHandler) {
      const refreshedToken = await this.refreshAccessToken();
      if (refreshedToken) {
        this.accessToken = refreshedToken;
        return this.requestArrayBuffer(path, init, false);
      }
    }

    if (!response.ok) {
      throw await this.toApiError(response);
    }

    return response.arrayBuffer();
  }

  private async requestText(
    path: string,
    init: RequestInit,
    retryAfterUnauthorized: boolean,
  ): Promise<string> {
    const response = await this.fetchResponse(path, init);

    if (response.status === 401 && retryAfterUnauthorized && this.unauthorizedHandler) {
      const refreshedToken = await this.refreshAccessToken();
      if (refreshedToken) {
        this.accessToken = refreshedToken;
        return this.requestText(path, init, false);
      }
    }

    if (!response.ok) {
      throw await this.toApiError(response);
    }

    return response.text();
  }

  private async fetchResponse(path: string, init: RequestInit): Promise<Response> {
    const url = `${this.baseUrl}${path}`;
    const requestInit: RequestInit = {
      ...init,
      credentials: 'include',
      headers: this.headers(init.headers),
    };
    const retryable = this.isSafeStartupRetry(init);
    const delays = retryable ? [0, ...this.startupRetryDelaysMs] : [0];
    for (let attempt = 0; attempt < delays.length; attempt += 1) {
      const delayMs = delays[attempt] ?? 0;
      if (delayMs > 0) {
        await this.delay(delayMs);
      }
      try {
        const response = await this.fetchImplementation(url, requestInit);
        if (
          retryable &&
          this.isStartupUnavailable(response) &&
          attempt < delays.length - 1
        ) {
          continue;
        }
        return response;
      } catch (error) {
        if (this.isAbortError(error)) {
          throw error;
        }
        if (!retryable || attempt === delays.length - 1) {
          throw new ApiError(
            0,
            'NETWORK_ERROR',
            'The server could not be reached. If the free server is starting, try again in a moment.',
          );
        }
      }
    }
    throw new ApiError(
      0,
      'NETWORK_ERROR',
      'The server could not be reached. If the free server is starting, try again in a moment.',
    );
  }

  private isSafeStartupRetry(init: RequestInit): boolean {
    const method = (init.method ?? 'GET').toUpperCase();
    return method === 'GET' || method === 'HEAD';
  }

  private isStartupUnavailable(response: Response): boolean {
    return [502, 503, 504].includes(response.status);
  }

  private isAbortError(error: unknown): boolean {
    return error instanceof Error && error.name === 'AbortError';
  }

  private delay(milliseconds: number): Promise<void> {
    return new Promise((resolve) => {
      setTimeout(resolve, milliseconds);
    });
  }

  private headers(input: HeadersInit | undefined): Headers {
    const headers = new Headers(input);
    if (!headers.has('Accept')) {
      headers.set('Accept', 'application/json');
    }
    headers.set('X-Client-Platform', this.platform);
    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    if (this.accessToken) {
      headers.set('Authorization', `Bearer ${this.accessToken}`);
    }
    return headers;
  }

  private refreshAccessToken(): Promise<string | null> {
    const handler = this.unauthorizedHandler;
    if (!handler) {
      return Promise.resolve(null);
    }
    if (!this.refreshInFlight) {
      this.refreshInFlight = handler().finally(() => {
        this.refreshInFlight = null;
      });
    }
    return this.refreshInFlight;
  }

  private async toApiError(response: Response): Promise<ApiError> {
    let body: ErrorBody = {};
    try {
      body = (await response.json()) as ErrorBody;
    } catch {
      // A malformed upstream error is still represented by a stable client error below.
    }
    return new ApiError(
      response.status,
      body.error?.code ?? this.defaultCode(response.status),
      body.error?.message ?? this.defaultMessage(response.status),
      body.error?.field_errors ?? {},
      body.error?.request_id ?? response.headers.get('X-Request-ID'),
    );
  }

  private defaultCode(status: number): string {
    return ({ 401: 'AUTHENTICATION_REQUIRED', 403: 'FORBIDDEN', 404: 'NOT_FOUND', 409: 'CONFLICT', 422: 'VALIDATION_ERROR' } as Record<number, string>)[status] ?? 'INTERNAL_SERVER_ERROR';
  }

  private defaultMessage(status: number): string {
    return status >= 500
      ? 'The server could not complete the request. Please try again.'
      : 'The request could not be completed. Check the information and try again.';
  }
}
