import { ApiError } from '@distributoros/api-client';

import { getErrorTranslationKey, type ErrorTranslationKey } from '@/features/auth/errorMessages';

import type { ProductField } from './validation';

export type ProductErrorTranslationKey =
  | ErrorTranslationKey
  | 'products.errors.duplicateName'
  | 'products.errors.duplicateSku'
  | 'products.errors.duplicateBarcode'
  | 'products.errors.notFound'
  | 'products.errors.unitLocked'
  | 'products.errors.invalidPage'
  | 'products.errors.saveFailed'
  | 'products.errors.stateChangeFailed';

export function getProductErrorTranslationKey(
  error: unknown,
  fallback: 'save' | 'state' | 'load' = 'load',
): ProductErrorTranslationKey {
  if (error instanceof ApiError) {
    const productKey = {
      PRODUCT_NAME_ALREADY_EXISTS: 'products.errors.duplicateName',
      PRODUCT_SKU_ALREADY_EXISTS: 'products.errors.duplicateSku',
      PRODUCT_BARCODE_ALREADY_EXISTS: 'products.errors.duplicateBarcode',
      PRODUCT_NOT_FOUND: 'products.errors.notFound',
      PRODUCT_UNIT_LOCKED: 'products.errors.unitLocked',
      INVALID_PRODUCT_CURSOR: 'products.errors.invalidPage',
    }[error.code] as ProductErrorTranslationKey | undefined;
    if (productKey) return productKey;
    const global = getErrorTranslationKey(error);
    if (global !== 'errors.unknown' && global !== 'errors.validation') return global;
  }
  if (fallback === 'save') return 'products.errors.saveFailed';
  if (fallback === 'state') return 'products.errors.stateChangeFailed';
  return getErrorTranslationKey(error);
}

export function setProductUniqueFieldError(
  error: unknown,
  setErrors: (errors: Partial<Record<ProductField, string>>) => void,
  translate: (key: string) => string,
) {
  if (!(error instanceof ApiError)) return;
  if (error.code === 'PRODUCT_NAME_ALREADY_EXISTS') {
    setErrors({ name: translate('products.validation.duplicateName') });
  } else if (error.code === 'PRODUCT_SKU_ALREADY_EXISTS') {
    setErrors({ sku: translate('products.validation.duplicateSku') });
  } else if (error.code === 'PRODUCT_BARCODE_ALREADY_EXISTS') {
    setErrors({ barcode: translate('products.validation.duplicateBarcode') });
  } else if (error.code === 'PRODUCT_UNIT_LOCKED') {
    setErrors({ unit: translate('products.validation.unitLocked') });
  }
}
