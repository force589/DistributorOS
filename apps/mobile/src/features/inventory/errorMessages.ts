import { ApiError } from '@distributoros/api-client';

import { getErrorTranslationKey, type ErrorTranslationKey } from '@/features/auth/errorMessages';

export type InventoryErrorTranslationKey =
  | ErrorTranslationKey
  | 'inventory.errors.productArchived'
  | 'inventory.errors.warehouseArchived'
  | 'inventory.errors.warehouseNotFound'
  | 'inventory.errors.insufficientStock'
  | 'inventory.errors.openingExists'
  | 'inventory.errors.invalidPage'
  | 'inventory.errors.submissionConflict'
  | 'inventory.errors.submissionFailed';

export function getInventoryErrorTranslationKey(
  error: unknown,
  fallback: 'load' | 'submit' = 'load',
): InventoryErrorTranslationKey {
  if (error instanceof ApiError) {
    const key = {
      PRODUCT_ARCHIVED: 'inventory.errors.productArchived',
      WAREHOUSE_ARCHIVED: 'inventory.errors.warehouseArchived',
      WAREHOUSE_NOT_FOUND: 'inventory.errors.warehouseNotFound',
      INSUFFICIENT_STOCK: 'inventory.errors.insufficientStock',
      OPENING_STOCK_ALREADY_RECORDED: 'inventory.errors.openingExists',
      INVALID_INVENTORY_CURSOR: 'inventory.errors.invalidPage',
      IDEMPOTENCY_KEY_REUSED: 'inventory.errors.submissionConflict',
    }[error.code] as InventoryErrorTranslationKey | undefined;
    if (key) return key;
    const global = getErrorTranslationKey(error);
    if (global !== 'errors.unknown' && global !== 'errors.validation') return global;
  }
  return fallback === 'submit'
    ? 'inventory.errors.submissionFailed'
    : getErrorTranslationKey(error);
}
