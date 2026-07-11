import { en } from './resources/en';

const requiredKeys = [
  'list.title',
  'list.create',
  'list.searchLabel',
  'list.dateLabel',
  'list.filterLabel',
  'list.sortLabel',
  'list.loadingTitle',
  'list.errorTitle',
  'list.emptyTitle',
  'filters.all',
  'sorts.newest',
  'sorts.oldest',
  'status.draft',
  'status.issued',
  'status.void',
  'create.title',
  'create.selectSale',
  'create.success',
  'details.title',
  'details.customer',
  'details.items',
  'details.totals',
  'details.draftNotice',
  'details.voidNotice',
  'issue.title',
  'issue.success',
  'void.title',
  'void.success',
  'pdf.preview',
  'pdf.share',
  'customerHistory.title',
  'customerHistory.viewInvoices',
  'validation.dateInvalid',
  'errors.notFound',
  'errors.alreadyExists',
  'errors.saleNotPosted',
  'errors.corruptState',
  'errors.pdfFailed',
] as const;

function valueAt(object: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((value, segment) => {
    if (!value || typeof value !== 'object') return undefined;
    return (value as Record<string, unknown>)[segment];
  }, object);
}

describe('invoice localization resources', () => {
  it.each(requiredKeys)('provides invoices.%s', (key) => {
    expect(valueAt(en.invoices, key)).toEqual(expect.any(String));
    expect(valueAt(en.invoices, key)).not.toBe('');
  });
});
