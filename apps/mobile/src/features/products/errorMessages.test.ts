import { ApiError } from '@distributoros/api-client';

import { getProductErrorTranslationKey } from './errorMessages';

describe('product error localization', () => {
  it.each([
    ['PRODUCT_NAME_ALREADY_EXISTS', 'products.errors.duplicateName'],
    ['PRODUCT_SKU_ALREADY_EXISTS', 'products.errors.duplicateSku'],
    ['PRODUCT_BARCODE_ALREADY_EXISTS', 'products.errors.duplicateBarcode'],
    ['PRODUCT_NOT_FOUND', 'products.errors.notFound'],
    ['PRODUCT_UNIT_LOCKED', 'products.errors.unitLocked'],
    ['INVALID_PRODUCT_CURSOR', 'products.errors.invalidPage'],
    ['NETWORK_ERROR', 'errors.network'],
  ])('maps %s to a stable localization key', (code, key) => {
    expect(getProductErrorTranslationKey(new ApiError(400, code, 'ignored'))).toBe(key);
  });

  it('uses action-specific localized fallbacks', () => {
    expect(getProductErrorTranslationKey(new Error('ignored'), 'save')).toBe(
      'products.errors.saveFailed',
    );
    expect(getProductErrorTranslationKey(new Error('ignored'), 'state')).toBe(
      'products.errors.stateChangeFailed',
    );
  });
});
