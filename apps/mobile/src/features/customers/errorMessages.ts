import { ApiError } from '@distributoros/api-client';

import { getErrorTranslationKey, type ErrorTranslationKey } from '@/features/auth/errorMessages';

export type CustomerErrorTranslationKey =
  | ErrorTranslationKey
  | 'customers.errors.duplicateName'
  | 'customers.errors.notFound'
  | 'customers.errors.invalidPage'
  | 'customers.errors.saveFailed'
  | 'customers.errors.stateChangeFailed';

export function getCustomerErrorTranslationKey(
  error: unknown,
  fallback: 'save' | 'state' | 'load' = 'load',
): CustomerErrorTranslationKey {
  if (error instanceof ApiError) {
    if (error.code === 'CUSTOMER_NAME_ALREADY_EXISTS') {
      return 'customers.errors.duplicateName';
    }
    if (error.code === 'CUSTOMER_NOT_FOUND') {
      return 'customers.errors.notFound';
    }
    if (error.code === 'INVALID_CUSTOMER_CURSOR') {
      return 'customers.errors.invalidPage';
    }
    const global = getErrorTranslationKey(error);
    if (global !== 'errors.unknown' && global !== 'errors.validation') {
      return global;
    }
  }
  if (fallback === 'save') return 'customers.errors.saveFailed';
  if (fallback === 'state') return 'customers.errors.stateChangeFailed';
  return getErrorTranslationKey(error);
}
