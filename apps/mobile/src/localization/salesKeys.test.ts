import { en } from './resources/en';

const requiredKeys = [
  'list.title',
  'list.searchLabel',
  'list.dateLabel',
  'list.emptyTitle',
  'list.errorTitle',
  'create.title',
  'create.success',
  'edit.title',
  'details.title',
  'details.postedNotice',
  'form.customer',
  'form.products',
  'form.removeTitle',
  'post.title',
  'post.success',
  'void.title',
  'void.success',
  'status.draft',
  'status.posted',
  'status.void',
  'validation.customerRequired',
  'validation.itemsRequired',
  'validation.quantityPrecision',
  'validation.pricePrecision',
  'errors.insufficientStock',
  'errors.notEditable',
  'errors.hasIssuedInvoice',
] as const;

function valueAt(object: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((value, segment) => {
    if (!value || typeof value !== 'object') return undefined;
    return (value as Record<string, unknown>)[segment];
  }, object);
}

describe('sales localization resources', () => {
  it.each(requiredKeys)('provides sales.%s', (key) => {
    expect(valueAt(en.sales, key)).toEqual(expect.any(String));
    expect(valueAt(en.sales, key)).not.toBe('');
  });
});
