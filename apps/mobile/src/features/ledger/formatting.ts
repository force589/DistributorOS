import type { LedgerEntryType } from '@distributoros/api-client';

import { formatLocalizedDate } from '@/formatting/presentation';

export const ledgerEntryTypeKeys: Record<
  Exclude<LedgerEntryType, 'all'> | 'SALE' | 'REVERSAL' | 'PAYMENT' | 'PAYMENT_REVERSAL',
  string
> = {
  sale: 'ledger.entryTypes.sale',
  reversal: 'ledger.entryTypes.reversal',
  payment: 'ledger.entryTypes.payment',
  payment_reversal: 'ledger.entryTypes.paymentReversal',
  SALE: 'ledger.entryTypes.sale',
  REVERSAL: 'ledger.entryTypes.reversal',
  PAYMENT: 'ledger.entryTypes.payment',
  PAYMENT_REVERSAL: 'ledger.entryTypes.paymentReversal',
};

export function formatLedgerDate(value: string, language: string): string {
  return formatLocalizedDate(value, language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

export function isValidLedgerDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value);
}
