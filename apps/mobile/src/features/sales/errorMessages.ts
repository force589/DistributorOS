import { ApiError } from '@distributoros/api-client';

import { getErrorTranslationKey, type ErrorTranslationKey } from '@/features/auth/errorMessages';

export type SaleErrorTranslationKey =
  | ErrorTranslationKey
  | 'sales.errors.notFound'
  | 'sales.errors.notEditable'
  | 'sales.errors.alreadyPosted'
  | 'sales.errors.alreadyVoided'
  | 'sales.errors.notPosted'
  | 'sales.errors.hasIssuedInvoice'
  | 'sales.errors.customerArchived'
  | 'sales.errors.customerNotFound'
  | 'sales.errors.productArchived'
  | 'sales.errors.productNotFound'
  | 'sales.errors.duplicateProduct'
  | 'sales.errors.insufficientStock'
  | 'sales.errors.warehouseUnavailable'
  | 'sales.errors.invalidPage'
  | 'sales.errors.submissionConflict'
  | 'sales.errors.editConflict'
  | 'sales.errors.inventoryHistoryMissing'
  | 'sales.errors.inventoryProjectionMissing'
  | 'sales.errors.ledgerCorrupt'
  | 'sales.errors.saveFailed'
  | 'sales.errors.loadFailed'
  | 'sales.errors.lifecycleFailed';

export function getSaleErrorTranslationKey(
  error: unknown,
  fallback: 'load' | 'save' | 'lifecycle' = 'load',
): SaleErrorTranslationKey {
  if (error instanceof ApiError) {
    const key = {
      SALE_NOT_FOUND: 'sales.errors.notFound',
      SALE_NOT_EDITABLE: 'sales.errors.notEditable',
      SALE_ALREADY_POSTED: 'sales.errors.alreadyPosted',
      SALE_ALREADY_VOIDED: 'sales.errors.alreadyVoided',
      SALE_NOT_POSTED: 'sales.errors.notPosted',
      SALE_HAS_ISSUED_INVOICE: 'sales.errors.hasIssuedInvoice',
      CUSTOMER_ARCHIVED: 'sales.errors.customerArchived',
      CUSTOMER_NOT_FOUND: 'sales.errors.customerNotFound',
      PRODUCT_ARCHIVED: 'sales.errors.productArchived',
      PRODUCT_NOT_FOUND: 'sales.errors.productNotFound',
      DUPLICATE_SALE_PRODUCT: 'sales.errors.duplicateProduct',
      INSUFFICIENT_STOCK: 'sales.errors.insufficientStock',
      DEFAULT_WAREHOUSE_UNAVAILABLE: 'sales.errors.warehouseUnavailable',
      INVALID_SALE_CURSOR: 'sales.errors.invalidPage',
      IDEMPOTENCY_KEY_REUSED: 'sales.errors.submissionConflict',
      SALE_EDIT_CONFLICT: 'sales.errors.editConflict',
      SALE_INVENTORY_HISTORY_MISSING: 'sales.errors.inventoryHistoryMissing',
      SALE_INVENTORY_PROJECTION_MISSING: 'sales.errors.inventoryProjectionMissing',
      LEDGER_STATE_CORRUPT: 'sales.errors.ledgerCorrupt',
    }[error.code] as SaleErrorTranslationKey | undefined;
    if (key) return key;
    const global = getErrorTranslationKey(error);
    if (global !== 'errors.unknown' && global !== 'errors.validation') return global;
  }
  if (fallback === 'save') return 'sales.errors.saveFailed';
  if (fallback === 'lifecycle') return 'sales.errors.lifecycleFailed';
  return 'sales.errors.loadFailed';
}
