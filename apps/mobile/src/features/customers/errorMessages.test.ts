import { ApiError } from '@distributoros/api-client';

import { getCustomerErrorTranslationKey } from './errorMessages';

describe('customer error localization', () => {
  it.each([
    ['CUSTOMER_NAME_ALREADY_EXISTS', 'customers.errors.duplicateName'],
    ['CUSTOMER_NOT_FOUND', 'customers.errors.notFound'],
    ['INVALID_CUSTOMER_CURSOR', 'customers.errors.invalidPage'],
    ['NETWORK_ERROR', 'errors.network'],
  ])('maps %s to a stable localization key', (code, key) => {
    expect(getCustomerErrorTranslationKey(new ApiError(400, code, 'ignored'))).toBe(key);
  });

  it('uses action-specific localized fallbacks', () => {
    expect(getCustomerErrorTranslationKey(new Error('ignored'), 'save')).toBe(
      'customers.errors.saveFailed',
    );
    expect(getCustomerErrorTranslationKey(new Error('ignored'), 'state')).toBe(
      'customers.errors.stateChangeFailed',
    );
  });
});
