import { ApiError } from '@distributoros/api-client';

import { getPaymentErrorTranslationKey } from './errorMessages';

describe('payment error localization', () => {
  it.each([
    ['PAYMENT_NOT_FOUND', 'payments.errors.notFound'],
    ['PAYMENT_ALREADY_VOIDED', 'payments.errors.alreadyVoided'],
    ['PAYMENT_ALLOCATION_TOTAL_INVALID', 'payments.errors.invalidAllocation'],
    ['PAYMENT_ALLOCATION_TARGET_REQUIRED', 'payments.errors.invalidAllocation'],
    ['PAYMENT_ALLOCATION_TARGET_NOT_FOUND', 'payments.errors.allocationTargetNotFound'],
    ['IDEMPOTENCY_KEY_REUSED', 'payments.errors.submissionConflict'],
    ['LEDGER_STATE_CORRUPT', 'payments.errors.ledgerCorrupt'],
    ['NETWORK_ERROR', 'errors.network'],
  ])('maps %s to a stable localization key', (code, key) => {
    expect(getPaymentErrorTranslationKey(new ApiError(400, code, 'ignored'))).toBe(key);
  });

  it('uses action-specific localized fallbacks', () => {
    expect(getPaymentErrorTranslationKey(new Error('ignored'), 'save')).toBe(
      'payments.errors.saveFailed',
    );
    expect(getPaymentErrorTranslationKey(new Error('ignored'), 'lifecycle')).toBe(
      'payments.errors.lifecycleFailed',
    );
  });
});
