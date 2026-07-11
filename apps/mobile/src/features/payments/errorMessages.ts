import { ApiError } from '@distributoros/api-client';

import { getErrorTranslationKey, type ErrorTranslationKey } from '@/features/auth/errorMessages';

export type PaymentErrorTranslationKey =
  | ErrorTranslationKey
  | 'payments.errors.notFound'
  | 'payments.errors.alreadyVoided'
  | 'payments.errors.customerArchived'
  | 'payments.errors.customerNotFound'
  | 'payments.errors.invalidAllocation'
  | 'payments.errors.duplicateAllocation'
  | 'payments.errors.allocationTargetNotFound'
  | 'payments.errors.invalidPage'
  | 'payments.errors.submissionConflict'
  | 'payments.errors.ledgerCorrupt'
  | 'payments.errors.saveFailed'
  | 'payments.errors.loadFailed'
  | 'payments.errors.lifecycleFailed';

export function getPaymentErrorTranslationKey(
  error: unknown,
  fallback: 'load' | 'save' | 'lifecycle' = 'load',
): PaymentErrorTranslationKey {
  if (error instanceof ApiError) {
    const key = {
      PAYMENT_NOT_FOUND: 'payments.errors.notFound',
      PAYMENT_ALREADY_VOIDED: 'payments.errors.alreadyVoided',
      CUSTOMER_ARCHIVED: 'payments.errors.customerArchived',
      CUSTOMER_NOT_FOUND: 'payments.errors.customerNotFound',
      PAYMENT_ALLOCATION_TOTAL_INVALID: 'payments.errors.invalidAllocation',
      PAYMENT_ALLOCATION_AMOUNT_INVALID: 'payments.errors.invalidAllocation',
      PAYMENT_ALLOCATION_TARGET_REQUIRED: 'payments.errors.invalidAllocation',
      DUPLICATE_PAYMENT_ALLOCATION: 'payments.errors.duplicateAllocation',
      PAYMENT_ALLOCATION_TARGET_NOT_FOUND: 'payments.errors.allocationTargetNotFound',
      INVALID_PAYMENT_CURSOR: 'payments.errors.invalidPage',
      IDEMPOTENCY_KEY_REUSED: 'payments.errors.submissionConflict',
      LEDGER_STATE_CORRUPT: 'payments.errors.ledgerCorrupt',
    }[error.code] as PaymentErrorTranslationKey | undefined;
    if (key) return key;
    const global = getErrorTranslationKey(error);
    if (global !== 'errors.unknown' && global !== 'errors.validation') return global;
  }
  if (fallback === 'save') return 'payments.errors.saveFailed';
  if (fallback === 'lifecycle') return 'payments.errors.lifecycleFailed';
  return 'payments.errors.loadFailed';
}
