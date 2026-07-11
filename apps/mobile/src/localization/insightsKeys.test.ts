import { en } from './resources/en';

const requiredKeys = [
  'dashboard.loadingTitle',
  'dashboard.errorTitle',
  'dashboard.globalSearch',
  'dashboard.recentSales',
  'metrics.todaySales',
  'metrics.outstandingReceivables',
  'metrics.inventoryValue',
  'search.title',
  'search.placeholder',
  'search.groups.customers',
  'search.groups.inventory',
  'reports.title',
  'reports.exportCsv',
  'reports.csvDownloaded',
  'reports.types.sales.title',
  'reports.types.payments.title',
  'reports.types.outstanding.title',
  'reports.types.inventory.title',
  'reports.types.lowStock.title',
  'reports.periods.custom',
  'reports.status.posted',
  'reports.sorts.highestOutstanding',
  'reports.sorts.lowestStock',
  'reports.stockStatus.out',
  'reports.validation.customDatesRequired',
  'errors.searchRequired',
  'errors.filterInvalid',
  'errors.invalidCursor',
  'errors.loadDashboard',
  'errors.exportCsv',
] as const;

function valueAt(object: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((value, segment) => {
    if (!value || typeof value !== 'object') return undefined;
    return (value as Record<string, unknown>)[segment];
  }, object);
}

describe('insights localization resources', () => {
  it.each(requiredKeys)('provides insights.%s', (key) => {
    expect(valueAt(en.insights, key)).toEqual(expect.any(String));
    expect(valueAt(en.insights, key)).not.toBe('');
  });
});
