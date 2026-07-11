import { en } from './resources/en';

const requiredKeys = [
  'list.title',
  'list.create',
  'list.searchLabel',
  'list.dateLabel',
  'list.filterLabel',
  'list.methodLabel',
  'list.sortLabel',
  'list.loadingTitle',
  'list.errorTitle',
  'list.emptyTitle',
  'filters.all',
  'status.posted',
  'status.void',
  'methods.all',
  'methods.cash',
  'methods.upi',
  'methods.bankTransfer',
  'methods.cheque',
  'methods.other',
  'sorts.newest',
  'sorts.oldest',
  'form.customer',
  'form.amount',
  'form.paymentMethod',
  'form.allocations',
  'form.loadingInvoices',
  'form.noInvoices',
  'form.allocatedAmount',
  'create.title',
  'create.success',
  'details.title',
  'details.voidNotice',
  'details.unallocatedAmount',
  'details.invoiceAllocation',
  'void.title',
  'void.success',
  'customerHistory.title',
  'customerHistory.viewPayments',
  'validation.customerRequired',
  'validation.dateInvalid',
  'validation.amountPrecision',
  'validation.allocationTotalTooLarge',
  'errors.invalidAllocation',
  'errors.submissionConflict',
  'errors.ledgerCorrupt',
  'errors.invoicePicker',
] as const;

function valueAt(object: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((value, segment) => {
    if (!value || typeof value !== 'object') return undefined;
    return (value as Record<string, unknown>)[segment];
  }, object);
}

describe('payment localization resources', () => {
  it.each(requiredKeys)('provides payments.%s', (key) => {
    expect(valueAt(en.payments, key)).toEqual(expect.any(String));
    expect(valueAt(en.payments, key)).not.toBe('');
  });
});
