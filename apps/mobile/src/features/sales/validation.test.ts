import { normalizeSale, type SaleDraft, validateSale } from './validation';

const validDraft = (): SaleDraft => ({
  customerId: 'customer-1',
  customerName: 'First Shop',
  items: [{
    productId: 'product-1',
    productName: 'Mango',
    unit: 'kg',
    quantity: '2.500',
    unitPrice: '12.50',
  }],
});

describe('sales validation', () => {
  it('requires a customer and at least one product', () => {
    expect(validateSale({ customerId: '', customerName: '', items: [] })).toEqual({
      customer_id: 'sales.validation.customerRequired',
      items: 'sales.validation.itemsRequired',
    });
  });

  it.each([
    ['quantity', '', 'sales.validation.quantityRequired'],
    ['quantity', 'abc', 'sales.validation.quantityInvalid'],
    ['quantity', '0', 'sales.validation.quantityPositive'],
    ['quantity', '1.2345', 'sales.validation.quantityPrecision'],
    ['unitPrice', '', 'sales.validation.priceRequired'],
    ['unitPrice', '-1', 'sales.validation.pricePositive'],
    ['unitPrice', '0', 'sales.validation.pricePositive'],
    ['unitPrice', '1.234', 'sales.validation.pricePrecision'],
  ] as const)('validates %s value %s', (field, value, expected) => {
    const draft = validDraft();
    draft.items[0] = { ...draft.items[0]!, [field]: value };
    const apiField = field === 'unitPrice' ? 'unit_price' : field;
    expect(validateSale(draft)[`items.0.${apiField}`]).toBe(expected);
  });

  it('rejects duplicate products and normalizes a valid request', () => {
    const draft = validDraft();
    draft.items.push({ ...draft.items[0]! });
    expect(validateSale(draft).items).toBe('sales.validation.duplicateProduct');
    draft.items.pop();
    draft.items[0]!.quantity = ' 2.500 ';
    draft.items[0]!.unitPrice = ' 12.50 ';
    expect(normalizeSale(draft)).toEqual({
      customer_id: 'customer-1',
      items: [{ product_id: 'product-1', quantity: '2.500', unit_price: '12.50' }],
    });
  });
});
