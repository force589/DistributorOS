import { ApiError } from '@distributoros/api-client';

import { getErrorTranslationKey, type ErrorTranslationKey } from '@/features/auth/errorMessages';

export type LedgerErrorTranslationKey =
  | ErrorTranslationKey
  | 'ledger.errors.corruptState'
  | 'ledger.errors.invalidPage'
  | 'ledger.errors.loadFailed';

export function getLedgerErrorTranslationKey(error: unknown): LedgerErrorTranslationKey {
  if (error instanceof ApiError) {
    if (error.code === 'LEDGER_STATE_CORRUPT') return 'ledger.errors.corruptState';
    if (error.code === 'INVALID_LEDGER_CURSOR') return 'ledger.errors.invalidPage';
    const global = getErrorTranslationKey(error);
    if (global !== 'errors.unknown' && global !== 'errors.validation') return global;
  }
  return 'ledger.errors.loadFailed';
}
