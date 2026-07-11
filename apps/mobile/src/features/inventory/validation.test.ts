import {
  isInventoryOperation,
  normalizeInventoryRequest,
  type InventoryDraft,
  validateInventoryDraft,
} from './validation';

describe('inventory validation', () => {
  const valid: InventoryDraft = { quantity: '2.500', notes: 'Count correction' };

  it('accepts signed adjustments but requires positive physical additions and removals', () => {
    expect(validateInventoryDraft({ ...valid, quantity: '-1.250' }, 'adjustment')).toEqual({});
    expect(validateInventoryDraft({ ...valid, quantity: '-1' }, 'receipt')).toEqual({
      quantity: 'inventory.validation.quantityPositive',
    });
  });

  it('returns field-specific keys for zero, precision, and adjustment reason', () => {
    expect(validateInventoryDraft({ quantity: '0', notes: '' }, 'adjustment')).toEqual({
      quantity: 'inventory.validation.quantityZero',
      notes: 'inventory.validation.reasonRequired',
    });
    expect(validateInventoryDraft({ quantity: '1.0001', notes: '' }, 'opening')).toEqual({
      quantity: 'inventory.validation.quantityPrecision',
    });
  });

  it('normalizes API payloads without introducing tenant or unit fields', () => {
    expect(normalizeInventoryRequest(valid, 'adjustment', 'product-1')).toEqual({
      product_id: 'product-1',
      quantity: '2.500',
      reason: 'Count correction',
    });
    expect(
      normalizeInventoryRequest({ quantity: '3', notes: ' ' }, 'receipt', 'product-1'),
    ).toEqual({
      product_id: 'product-1',
      quantity: '3',
      remarks: null,
    });
  });

  it('recognizes only Phase 4 operations', () => {
    expect(isInventoryOperation('spoilage')).toBe(true);
    expect(isInventoryOperation('sale')).toBe(false);
  });
});
