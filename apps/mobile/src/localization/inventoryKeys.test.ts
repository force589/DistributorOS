import { en } from './resources/en';

const requiredKeys = [
  'list.title',
  'list.searchLabel',
  'list.emptyTitle',
  'list.errorTitle',
  'details.title',
  'details.operationsTitle',
  'operations.opening',
  'operations.receipt',
  'operations.adjustment',
  'operations.customerReturn',
  'operations.damage',
  'operations.spoilage',
  'operations.confirmTitle',
  'history.title',
  'history.emptyTitle',
  'movementTypes.openingStock',
  'movementTypes.spoilage',
  'movementTypes.sale',
  'movementTypes.saleVoid',
  'status.outOfStock',
  'status.lowStock',
  'status.normal',
  'validation.quantityRequired',
  'validation.reasonRequired',
  'errors.insufficientStock',
  'errors.openingExists',
] as const;

function valueAt(object: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((value, segment) => {
    if (!value || typeof value !== 'object') return undefined;
    return (value as Record<string, unknown>)[segment];
  }, object);
}

describe('inventory localization resources', () => {
  it.each(requiredKeys)('provides inventory.%s', (key) => {
    expect(valueAt(en.inventory, key)).toEqual(expect.any(String));
    expect(valueAt(en.inventory, key)).not.toBe('');
  });
});
