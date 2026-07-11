import type { ProductDraft } from './validation';
import { normalizeProduct, validateProduct } from './validation';

const valid: ProductDraft = {
  name: 'Mineral Water',
  sku: 'WATER-20L',
  barcode: '8901234567890',
  category: 'Beverages',
  description: 'Twenty litre container',
  selling_price: '125.50',
  unit: 'litre',
  low_stock_threshold: '2.500',
};

describe('product validation', () => {
  it('accepts decimal product information', () => {
    expect(validateProduct(valid)).toEqual({});
  });

  it('returns field-specific keys for required, negative, precision, and length rules', () => {
    expect(
      validateProduct({
        name: '',
        sku: 'x'.repeat(101),
        barcode: 'x'.repeat(129),
        category: 'x'.repeat(101),
        description: 'x'.repeat(2001),
        selling_price: '-1',
        unit: '',
        low_stock_threshold: '0.0001',
      }),
    ).toEqual({
      name: 'products.validation.nameRequired',
      sku: 'products.validation.skuTooLong',
      barcode: 'products.validation.barcodeTooLong',
      category: 'products.validation.categoryTooLong',
      description: 'products.validation.descriptionTooLong',
      selling_price: 'products.validation.sellingPriceNegative',
      unit: 'products.validation.unitRequired',
      low_stock_threshold: 'products.validation.thresholdPrecision',
    });
  });

  it('normalizes optional values without changing decimal strings', () => {
    expect(
      normalizeProduct({
        ...valid,
        name: '  Mineral Water  ',
        sku: ' ',
        description: '  Twenty litre container  ',
      }),
    ).toMatchObject({
      name: 'Mineral Water',
      sku: null,
      description: 'Twenty litre container',
      selling_price: '125.50',
      low_stock_threshold: '2.500',
    });
  });
});
