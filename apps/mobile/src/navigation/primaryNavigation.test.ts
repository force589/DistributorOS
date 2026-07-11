import {
  getActivePrimaryNavigationKey,
  shouldNavigateToPrimaryRoute,
} from './primaryNavigation';

describe('primary navigation routing', () => {
  it.each([
    ['/', 'home'],
    ['/sales', 'sales'],
    ['/sales/SALE-000001', 'sales'],
    ['/customers/CUST-000001', 'customers'],
    ['/products/new', 'products'],
    ['/inventory', 'more'],
    ['/payments/PAY-000001', 'more'],
    ['/invoices', 'more'],
    ['/reports/sales', 'more'],
    ['/search', 'more'],
    ['/settings', 'more'],
    ['/more', 'more'],
  ])('maps %s to %s', (pathname, expected) => {
    expect(getActivePrimaryNavigationKey(pathname)).toBe(expected);
  });

  it('does not navigate or remount an already active primary destination', () => {
    expect(shouldNavigateToPrimaryRoute('/', '/')).toBe(false);
    expect(shouldNavigateToPrimaryRoute('/sales', '/sales')).toBe(false);
    expect(shouldNavigateToPrimaryRoute('/sales/SALE-000001', '/sales')).toBe(true);
  });
});
