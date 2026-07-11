import { ApiError } from '@distributoros/api-client';

import { getLedgerErrorTranslationKey } from './errorMessages';

describe('ledger error localization', () => {
  it('maps corruption and cursor errors to actionable messages', () => {
    expect(
      getLedgerErrorTranslationKey(new ApiError(409, 'LEDGER_STATE_CORRUPT', 'failure')),
    ).toBe('ledger.errors.corruptState');
    expect(
      getLedgerErrorTranslationKey(new ApiError(422, 'INVALID_LEDGER_CURSOR', 'failure')),
    ).toBe('ledger.errors.invalidPage');
  });

  it('uses a ledger-specific fallback', () => {
    expect(getLedgerErrorTranslationKey(new Error('failure'))).toBe(
      'ledger.errors.loadFailed',
    );
  });
});
