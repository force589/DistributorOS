import type { ProductUnit } from '@distributoros/api-client';
import { formatCurrency, getActiveCurrency } from '@/formatting/presentation';

export const productUnitKeys: Record<ProductUnit, string> = {
  piece: 'products.units.piece',
  kg: 'products.units.kg',
  gram: 'products.units.gram',
  litre: 'products.units.litre',
  millilitre: 'products.units.millilitre',
  box: 'products.units.box',
  packet: 'products.units.packet',
  dozen: 'products.units.dozen',
};

export function formatInr(value: string, language: string, currency: string = getActiveCurrency()): string {
  return formatCurrency(value, currency, language);
}
