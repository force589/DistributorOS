import type { ProductCreateRequest, ProductUnit } from '@distributoros/api-client';

export type ProductField = keyof ProductCreateRequest;
export type ProductValidationKey =
  | 'products.validation.nameRequired'
  | 'products.validation.nameTooLong'
  | 'products.validation.skuTooLong'
  | 'products.validation.barcodeTooLong'
  | 'products.validation.categoryTooLong'
  | 'products.validation.descriptionTooLong'
  | 'products.validation.sellingPriceRequired'
  | 'products.validation.sellingPriceInvalid'
  | 'products.validation.sellingPriceNegative'
  | 'products.validation.sellingPricePrecision'
  | 'products.validation.sellingPriceTooLarge'
  | 'products.validation.unitRequired'
  | 'products.validation.unitInvalid'
  | 'products.validation.thresholdRequired'
  | 'products.validation.thresholdInvalid'
  | 'products.validation.thresholdNegative'
  | 'products.validation.thresholdPrecision'
  | 'products.validation.thresholdTooLarge';

export type ProductValidationErrors = Partial<Record<ProductField, ProductValidationKey>>;

export interface ProductDraft {
  name: string;
  sku: string;
  barcode: string;
  category: string;
  description: string;
  selling_price: string;
  unit: ProductUnit | '';
  low_stock_threshold: string;
}

export const productUnits: ProductUnit[] = [
  'piece',
  'kg',
  'gram',
  'litre',
  'millilitre',
  'box',
  'packet',
  'dozen',
];

const decimalPattern = /^(?:\d+(?:\.\d*)?|\.\d+)$/;

function validateDecimal(
  value: string,
  {
    field,
    decimalPlaces,
    maxValue,
  }: {
    field: 'selling_price' | 'low_stock_threshold';
    decimalPlaces: number;
    maxValue: number;
  },
): ProductValidationKey | undefined {
  const prefix = field === 'selling_price' ? 'sellingPrice' : 'threshold';
  if (!value.trim()) {
    return `products.validation.${prefix}Required` as ProductValidationKey;
  }
  if (!decimalPattern.test(value.trim())) {
    if (value.trim().startsWith('-') && Number(value) < 0) {
      return `products.validation.${prefix}Negative` as ProductValidationKey;
    }
    return `products.validation.${prefix}Invalid` as ProductValidationKey;
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return `products.validation.${prefix}Invalid` as ProductValidationKey;
  }
  if (number < 0) {
    return `products.validation.${prefix}Negative` as ProductValidationKey;
  }
  if ((value.split('.')[1]?.length ?? 0) > decimalPlaces) {
    return `products.validation.${prefix}Precision` as ProductValidationKey;
  }
  if (number > maxValue) {
    return `products.validation.${prefix}TooLarge` as ProductValidationKey;
  }
  return undefined;
}

export function validateProduct(product: ProductDraft): ProductValidationErrors {
  const errors: ProductValidationErrors = {};
  const name = product.name.trim();
  if (!name) errors.name = 'products.validation.nameRequired';
  else if (name.length > 160) errors.name = 'products.validation.nameTooLong';
  if (product.sku.trim().length > 100) errors.sku = 'products.validation.skuTooLong';
  if (product.barcode.trim().length > 128) {
    errors.barcode = 'products.validation.barcodeTooLong';
  }
  if (product.category.trim().length > 100) {
    errors.category = 'products.validation.categoryTooLong';
  }
  if (product.description.trim().length > 2000) {
    errors.description = 'products.validation.descriptionTooLong';
  }
  errors.selling_price = validateDecimal(product.selling_price, {
    field: 'selling_price',
    decimalPlaces: 2,
    maxValue: 999999999999.99,
  });
  errors.low_stock_threshold = validateDecimal(product.low_stock_threshold, {
    field: 'low_stock_threshold',
    decimalPlaces: 3,
    maxValue: 999999999999999.999,
  });
  if (!product.unit) errors.unit = 'products.validation.unitRequired';
  else if (!productUnits.includes(product.unit)) {
    errors.unit = 'products.validation.unitInvalid';
  }
  return Object.fromEntries(
    Object.entries(errors).filter(([, value]) => value !== undefined),
  ) as ProductValidationErrors;
}

export function normalizeProduct(product: ProductDraft): ProductCreateRequest {
  const optional = (value: string): string | null => value.trim() || null;
  return {
    name: product.name.trim(),
    sku: optional(product.sku),
    barcode: optional(product.barcode),
    category: optional(product.category),
    description: optional(product.description),
    selling_price: product.selling_price.trim(),
    unit: product.unit as ProductUnit,
    low_stock_threshold: product.low_stock_threshold.trim(),
  };
}
