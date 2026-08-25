import { en } from './resources/en';

const requiredKeys = [
  'summary.title',
  'summary.outstandingBalance',
  'summary.availableCredit',
  'summary.totalSales',
  'summary.totalPayments',
  'summary.lastSaleDate',
  'summary.lastPaymentDate',
  'summary.viewLedger',
  'list.title',
  'list.searchLabel',
  'list.dateLabel',
  'list.typeLabel',
  'list.loadingTitle',
  'list.errorTitle',
  'list.emptyTitle',
  'filters.all',
  'filters.sale',
  'filters.reversal',
  'filters.payment',
  'filters.paymentReversal',
  'entryTypes.sale',
  'entryTypes.reversal',
  'entryTypes.payment',
  'entryTypes.paymentReversal',
  'fields.debit',
  'fields.credit',
  'fields.runningBalance',
  'fields.openReference',
  'validation.dateInvalid',
  'errors.corruptState',
  'errors.invalidPage',
] as const;

function valueAt(object: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((value, segment) => {
    if (!value || typeof value !== 'object') return undefined;
    return (value as Record<string, unknown>)[segment];
  }, object);
}

describe('ledger localization resources', () => {
  it.each(requiredKeys)('provides ledger.%s', (key) => {
    expect(valueAt(en.ledger, key)).toEqual(expect.any(String));
    expect(valueAt(en.ledger, key)).not.toBe('');
  });
});
