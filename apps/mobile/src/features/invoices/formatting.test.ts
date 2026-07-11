import type { InvoiceListItem } from '@distributoros/api-client';

import {
  formatInvoiceDate,
  formatInvoiceDateTime,
  invoiceRowKey,
  invoiceStatusKeys,
} from './formatting';

describe('invoice formatting', () => {
  it('maps invoice statuses to localization keys', () => {
    expect(invoiceStatusKeys.DRAFT).toBe('invoices.status.draft');
    expect(invoiceStatusKeys.ISSUED).toBe('invoices.status.issued');
    expect(invoiceStatusKeys.VOID).toBe('invoices.status.void');
    expect(invoiceStatusKeys.draft).toBe('invoices.status.draft');
  });

  it('formats invoice dates and date-times for display', () => {
    expect(formatInvoiceDate('2026-06-30', 'en-IN')).toContain('2026');
    expect(formatInvoiceDateTime('2026-06-30T05:30:00.000Z', 'en-IN')).toContain('2026');
  });

  it('uses the human invoice number as the row key', () => {
    expect(invoiceRowKey({ invoice_number: 'INV-000001' } as InvoiceListItem)).toBe(
      'INV-000001',
    );
  });
});
