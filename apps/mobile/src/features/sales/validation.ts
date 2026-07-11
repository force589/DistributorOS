import type { SaleCreateRequest } from '@distributoros/api-client';

export interface SaleDraftLine {
  productId: string;
  productName: string;
  unit: string;
  quantity: string;
  unitPrice: string;
}

export interface SaleDraft {
  customerId: string;
  customerName: string;
  items: SaleDraftLine[];
}

export type SaleValidationKey =
  | 'sales.validation.customerRequired'
  | 'sales.validation.itemsRequired'
  | 'sales.validation.itemsTooMany'
  | 'sales.validation.duplicateProduct'
  | 'sales.validation.quantityRequired'
  | 'sales.validation.quantityInvalid'
  | 'sales.validation.quantityPositive'
  | 'sales.validation.quantityPrecision'
  | 'sales.validation.quantityTooLarge'
  | 'sales.validation.priceRequired'
  | 'sales.validation.priceInvalid'
  | 'sales.validation.pricePositive'
  | 'sales.validation.pricePrecision'
  | 'sales.validation.priceTooLarge';

export type SaleValidationErrors = Record<string, SaleValidationKey>;

const decimalPattern = /^(?:\d+(?:\.\d*)?|\.\d+)$/;

function validatePositiveDecimal(
  value: string,
  kind: 'quantity' | 'price',
  decimalPlaces: number,
  maximum: number,
): SaleValidationKey | undefined {
  const trimmed = value.trim();
  if (!trimmed) return `sales.validation.${kind}Required`;
  if (trimmed.startsWith('-') && Number.isFinite(Number(trimmed))) {
    return `sales.validation.${kind}Positive`;
  }
  if (!decimalPattern.test(trimmed) || !Number.isFinite(Number(trimmed))) {
    return `sales.validation.${kind}Invalid`;
  }
  if (Number(trimmed) <= 0) return `sales.validation.${kind}Positive`;
  if ((trimmed.split('.')[1]?.length ?? 0) > decimalPlaces) {
    return `sales.validation.${kind}Precision`;
  }
  if (Number(trimmed) > maximum) return `sales.validation.${kind}TooLarge`;
  return undefined;
}

export function validateSale(draft: SaleDraft): SaleValidationErrors {
  const errors: SaleValidationErrors = {};
  if (!draft.customerId) errors.customer_id = 'sales.validation.customerRequired';
  if (draft.items.length === 0) errors.items = 'sales.validation.itemsRequired';
  if (draft.items.length > 100) errors.items = 'sales.validation.itemsTooMany';
  const productIds = new Set<string>();
  draft.items.forEach((item, index) => {
    if (productIds.has(item.productId)) {
      errors.items = 'sales.validation.duplicateProduct';
    }
    productIds.add(item.productId);
    const quantityError = validatePositiveDecimal(
      item.quantity,
      'quantity',
      3,
      99999999999999999.999,
    );
    const priceError = validatePositiveDecimal(
      item.unitPrice,
      'price',
      2,
      999999999999.99,
    );
    if (quantityError) errors[`items.${index}.quantity`] = quantityError;
    if (priceError) errors[`items.${index}.unit_price`] = priceError;
  });
  return errors;
}

export function normalizeSale(draft: SaleDraft): SaleCreateRequest {
  return {
    customer_id: draft.customerId,
    items: draft.items.map((item) => ({
      product_id: item.productId,
      quantity: item.quantity.trim(),
      unit_price: item.unitPrice.trim(),
    })),
  };
}
