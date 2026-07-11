import type { AdjustmentRequest, PositiveStockRequest } from '@distributoros/api-client';

export type InventoryOperation =
  | 'opening'
  | 'receipt'
  | 'adjustment'
  | 'customerReturn'
  | 'damage'
  | 'spoilage';

export interface InventoryDraft {
  quantity: string;
  notes: string;
}

export type InventoryField = keyof InventoryDraft;
export type InventoryValidationKey =
  | 'inventory.validation.quantityRequired'
  | 'inventory.validation.quantityInvalid'
  | 'inventory.validation.quantityPositive'
  | 'inventory.validation.quantityZero'
  | 'inventory.validation.quantityPrecision'
  | 'inventory.validation.quantityTooLarge'
  | 'inventory.validation.reasonRequired'
  | 'inventory.validation.remarksTooLong';
export type InventoryValidationErrors = Partial<
  Record<InventoryField, InventoryValidationKey>
>;

const signedDecimal = /^-?(?:\d+(?:\.\d*)?|\.\d+)$/;
const positiveDecimal = /^(?:\d+(?:\.\d*)?|\.\d+)$/;

export function isInventoryOperation(value: string | undefined): value is InventoryOperation {
  return [
    'opening',
    'receipt',
    'adjustment',
    'customerReturn',
    'damage',
    'spoilage',
  ].includes(value ?? '');
}

export function validateInventoryDraft(
  draft: InventoryDraft,
  operation: InventoryOperation,
): InventoryValidationErrors {
  const errors: InventoryValidationErrors = {};
  const quantity = draft.quantity.trim();
  if (!quantity) {
    errors.quantity = 'inventory.validation.quantityRequired';
  } else if (!(operation === 'adjustment' ? signedDecimal : positiveDecimal).test(quantity)) {
    errors.quantity =
      quantity.startsWith('-') && operation !== 'adjustment'
        ? 'inventory.validation.quantityPositive'
        : 'inventory.validation.quantityInvalid';
  } else {
    const number = Number(quantity);
    if (!Number.isFinite(number)) {
      errors.quantity = 'inventory.validation.quantityInvalid';
    } else if (number === 0) {
      errors.quantity = 'inventory.validation.quantityZero';
    } else if (operation !== 'adjustment' && number < 0) {
      errors.quantity = 'inventory.validation.quantityPositive';
    } else if ((quantity.split('.')[1]?.length ?? 0) > 3) {
      errors.quantity = 'inventory.validation.quantityPrecision';
    } else if (Math.abs(number) > 99999999999999999.999) {
      errors.quantity = 'inventory.validation.quantityTooLarge';
    }
  }
  if (operation === 'adjustment' && !draft.notes.trim()) {
    errors.notes = 'inventory.validation.reasonRequired';
  } else if (draft.notes.trim().length > 1000) {
    errors.notes = 'inventory.validation.remarksTooLong';
  }
  return errors;
}

export function normalizeInventoryRequest(
  draft: InventoryDraft,
  operation: InventoryOperation,
  productId: string,
): PositiveStockRequest | AdjustmentRequest {
  if (operation === 'adjustment') {
    return {
      product_id: productId,
      quantity: draft.quantity.trim(),
      reason: draft.notes.trim(),
    };
  }
  return {
    product_id: productId,
    quantity: draft.quantity.trim(),
    remarks: draft.notes.trim() || null,
  };
}
