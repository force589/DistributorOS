import type {
  LowStockStatus,
  MovementType,
  ProductUnit,
} from '@distributoros/api-client';

import { productUnitKeys } from '@/features/products/formatting';
import { formatLocalizedDate } from '@/formatting/presentation';

export const lowStockStatusKeys: Record<LowStockStatus, string> = {
  OUT_OF_STOCK: 'inventory.status.outOfStock',
  LOW_STOCK: 'inventory.status.lowStock',
  NORMAL: 'inventory.status.normal',
};

export const movementTypeKeys: Record<MovementType, string> = {
  OPENING_STOCK: 'inventory.movementTypes.openingStock',
  STOCK_RECEIPT: 'inventory.movementTypes.stockReceipt',
  STOCK_ADJUSTMENT: 'inventory.movementTypes.stockAdjustment',
  CUSTOMER_RETURN: 'inventory.movementTypes.customerReturn',
  DAMAGED: 'inventory.movementTypes.damaged',
  SPOILAGE: 'inventory.movementTypes.spoilage',
  SALE: 'inventory.movementTypes.sale',
  SALE_VOID: 'inventory.movementTypes.saleVoid',
};

export function formatQuantity(value: string, language: string): string {
  return new Intl.NumberFormat(language, { maximumFractionDigits: 3 }).format(Number(value));
}

export function formatStockQuantity(
  value: string,
  unit: string,
  language: string,
  translate: (key: string) => string,
): string {
  const unitKey = productUnitKeys[unit as ProductUnit];
  return `${formatQuantity(value, language)} ${unitKey ? translate(unitKey) : unit}`;
}

export function formatInventoryDate(value: string, language: string): string {
  return formatLocalizedDate(value, language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}
