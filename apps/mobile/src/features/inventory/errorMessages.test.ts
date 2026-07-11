import { ApiError } from '@distributoros/api-client';

import { getInventoryErrorTranslationKey } from './errorMessages';

describe('inventory error localization', () => {
  it.each([
    ['PRODUCT_ARCHIVED', 'inventory.errors.productArchived'],
    ['WAREHOUSE_ARCHIVED', 'inventory.errors.warehouseArchived'],
    ['WAREHOUSE_NOT_FOUND', 'inventory.errors.warehouseNotFound'],
    ['INSUFFICIENT_STOCK', 'inventory.errors.insufficientStock'],
    ['OPENING_STOCK_ALREADY_RECORDED', 'inventory.errors.openingExists'],
    ['INVALID_INVENTORY_CURSOR', 'inventory.errors.invalidPage'],
    ['IDEMPOTENCY_KEY_REUSED', 'inventory.errors.submissionConflict'],
    ['NETWORK_ERROR', 'errors.network'],
  ])('maps %s to %s', (code, key) => {
    expect(getInventoryErrorTranslationKey(new ApiError(400, code, 'ignored'))).toBe(key);
  });

  it('uses a specific submission fallback', () => {
    expect(getInventoryErrorTranslationKey(new Error('ignored'), 'submit')).toBe(
      'inventory.errors.submissionFailed',
    );
  });
});
