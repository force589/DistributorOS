import type { InvoiceListItem, InvoiceStatus } from '@distributoros/api-client';

import { formatLocalizedDate } from '@/formatting/presentation';

export const invoiceStatusKeys: Record<
  Exclude<InvoiceStatus, 'all'> | 'DRAFT' | 'ISSUED' | 'VOID',
  string
> = {
  draft: 'invoices.status.draft',
  issued: 'invoices.status.issued',
  void: 'invoices.status.void',
  DRAFT: 'invoices.status.draft',
  ISSUED: 'invoices.status.issued',
  VOID: 'invoices.status.void',
};

export function formatInvoiceDate(value: string, language: string): string {
  return formatLocalizedDate(value, language, {
    dateStyle: 'medium',
  });
}

export function formatInvoiceDateTime(value: string, language: string): string {
  return formatLocalizedDate(value, language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

export function invoiceRowKey(invoice: InvoiceListItem): string {
  return invoice.invoice_number;
}
