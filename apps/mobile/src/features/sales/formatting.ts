import type { SaleListItem, SaleStatus } from '@distributoros/api-client';
import {
  formatCurrency,
  formatLocalizedDate,
  getActiveCurrency,
} from '@/formatting/presentation';

export const saleStatusKeys: Record<Exclude<SaleStatus, 'all'> | 'DRAFT' | 'POSTED' | 'VOID', string> = {
  draft: 'sales.status.draft',
  posted: 'sales.status.posted',
  void: 'sales.status.void',
  DRAFT: 'sales.status.draft',
  POSTED: 'sales.status.posted',
  VOID: 'sales.status.void',
};

export function formatInr(value: string, language: string, currency: string = getActiveCurrency()): string {
  return formatCurrency(value, currency, language);
}

export function formatSaleDate(value: string, language: string): string {
  return formatLocalizedDate(value, language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

export function saleRowKey(sale: SaleListItem): string {
  return sale.sale_number;
}
