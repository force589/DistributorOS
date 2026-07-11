import { ApiError } from '@distributoros/api-client';

import { getSaleErrorTranslationKey } from './errorMessages';

describe('sales API error localization', () => {
  it.each([
    ['SALE_NOT_EDITABLE', 'sales.errors.notEditable'],
    ['INSUFFICIENT_STOCK', 'sales.errors.insufficientStock'],
    ['CUSTOMER_ARCHIVED', 'sales.errors.customerArchived'],
    ['PRODUCT_ARCHIVED', 'sales.errors.productArchived'],
    ['INVALID_SALE_CURSOR', 'sales.errors.invalidPage'],
    ['IDEMPOTENCY_KEY_REUSED', 'sales.errors.submissionConflict'],
    ['SALE_INVENTORY_PROJECTION_MISSING', 'sales.errors.inventoryProjectionMissing'],
    ['SALE_HAS_ISSUED_INVOICE', 'sales.errors.hasIssuedInvoice'],
    ['LEDGER_STATE_CORRUPT', 'sales.errors.ledgerCorrupt'],
  ])('maps %s to %s', (code, key) => {
    expect(getSaleErrorTranslationKey(new ApiError(409, code, 'failure'))).toBe(key);
  });

  it('uses action-specific fallbacks without generic messages', () => {
    expect(getSaleErrorTranslationKey(new Error('failure'), 'save')).toBe(
      'sales.errors.saveFailed',
    );
    expect(getSaleErrorTranslationKey(new Error('failure'), 'lifecycle')).toBe(
      'sales.errors.lifecycleFailed',
    );
  });
});
