import { en } from './resources/en';

const requiredProductKeys = [
  'list.title',
  'list.create',
  'list.searchLabel',
  'list.emptyTitle',
  'list.errorTitle',
  'create.action',
  'create.success',
  'edit.action',
  'edit.success',
  'details.title',
  'archive.title',
  'restore.title',
  'validation.nameRequired',
  'validation.sellingPriceNegative',
  'validation.unitInvalid',
  'validation.unitLocked',
  'validation.duplicateSku',
  'validation.duplicateBarcode',
  'errors.notFound',
  'units.piece',
  'units.kg',
  'units.dozen',
] as const;

function valueAt(object: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((value, segment) => {
    if (!value || typeof value !== 'object') return undefined;
    return (value as Record<string, unknown>)[segment];
  }, object);
}

describe('product localization resources', () => {
  it.each(requiredProductKeys)('provides products.%s', (key) => {
    expect(valueAt(en.products, key)).toEqual(expect.any(String));
    expect(valueAt(en.products, key)).not.toBe('');
  });
});
