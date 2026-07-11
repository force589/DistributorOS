import { en } from './resources/en';

const requiredCustomerKeys = [
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
  'archive.success',
  'restore.title',
  'restore.success',
  'validation.nameRequired',
  'validation.duplicateName',
  'validation.emailInvalid',
  'validation.phoneInvalid',
  'errors.notFound',
] as const;

function valueAt(object: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((value, segment) => {
    if (!value || typeof value !== 'object') return undefined;
    return (value as Record<string, unknown>)[segment];
  }, object);
}

describe('customer localization resources', () => {
  it.each(requiredCustomerKeys)('provides customers.%s', (key) => {
    expect(valueAt(en.customers, key)).toEqual(expect.any(String));
    expect(valueAt(en.customers, key)).not.toBe('');
  });
});
