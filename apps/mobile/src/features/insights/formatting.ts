import { formatCurrency, formatLocalizedDate, formatNumber } from '@/formatting/presentation';

export const formatMoney = formatCurrency;

export function formatQuantity(value: string | number | null | undefined, unit?: string): string {
  const formatted = formatNumber(value);
  return unit ? `${formatted} ${unit}` : formatted;
}

export function formatDate(value: string | null | undefined): string {
  return formatLocalizedDate(value, undefined, { dateStyle: 'medium' });
}

export function formatDateTime(value: string | null | undefined): string {
  return formatLocalizedDate(value, undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}
