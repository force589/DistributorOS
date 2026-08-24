import '@/localization/i18n';

import type { Dashboard } from '@distributoros/api-client';
import { useQuery } from '@tanstack/react-query';
import { fireEvent, render } from '@testing-library/react-native';

import DashboardScreen from '../../../app/(app)/index';

const mockNavigate = jest.fn();

jest.mock('@tanstack/react-query', () => ({ useQuery: jest.fn() }));
jest.mock('expo-router', () => ({
  useRouter: () => ({ navigate: mockNavigate, push: jest.fn() }),
}));
jest.mock('@/design/responsive', () => ({
  useResponsiveLayout: () => ({
    contentMaxWidth: 680,
    isDesktop: false,
    isPhone: true,
    isTablet: false,
    quickActionColumns: 2,
  }),
}));
jest.mock('@/features/auth/AuthContext', () => ({
  useAuth: () => ({ user: { business: { business_name: 'Test Distributor' } } }),
}));

const metric = { label: 'Metric', unit: 'count' as const, value: '0' };
const dashboard: Dashboard = {
  active_products: metric,
  business_date: '2026-07-02',
  currency: 'INR',
  customer_credit: { ...metric, unit: 'money' },
  highest_outstanding_customers: [],
  inventory_value: { ...metric, unit: 'money' },
  low_stock_products: metric,
  out_of_stock_products: metric,
  outstanding_receivables: { ...metric, unit: 'money' },
  recent_inventory_activity: [],
  recent_invoices: [],
  recent_payments: [],
  recent_sales: [],
  timezone: 'Asia/Kolkata',
  today_collections: { ...metric, unit: 'money' },
  today_sales: { ...metric, unit: 'money' },
  top_selling_products: [],
  total_customers: metric,
};

describe('dashboard navigation redesign', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    jest.mocked(useQuery).mockClear();
    jest.mocked(useQuery).mockReturnValue({
      data: dashboard,
      isError: false,
      isFetching: false,
      isPending: false,
      isRefetching: false,
      refetch: jest.fn(),
    } as unknown as ReturnType<typeof useQuery>);
  });

  it('keeps all KPIs and places Quick Actions before activity sections', async () => {
    const screen = await render(<DashboardScreen />);
    const renderedText = collectText(screen.toJSON());

    expect(renderedText).toContain("Today's Sales");
    expect(renderedText).toContain('Out of Stock Products');
    expect(renderedText.indexOf('Quick Actions')).toBeGreaterThan(
      renderedText.indexOf('Out of Stock Products'),
    );
    expect(renderedText.indexOf('Quick Actions')).toBeLessThan(
      renderedText.indexOf('Recent Sales'),
    );
    expect(renderedText.indexOf('Recent Sales')).toBeLessThan(
      renderedText.indexOf('Recent Payments'),
    );
    expect(renderedText.indexOf('Recent Payments')).toBeLessThan(
      renderedText.indexOf('Recent Invoices'),
    );
    expect(screen.queryByText('Manage Customers')).toBeNull();
  });

  it('opens every core module directly from its quick action', async () => {
    const screen = await render(<DashboardScreen />);
    const destinations = [
      ['Customers', '/customers'],
      ['Products', '/products'],
      ['Inventory', '/inventory'],
      ['Sales', '/sales'],
      ['Payments', '/payments'],
      ['Invoices', '/invoices'],
    ] as const;

    for (const [label, route] of destinations) {
      await fireEvent.press(screen.getByRole('button', { name: label }));
      expect(mockNavigate).toHaveBeenLastCalledWith(route);
    }
    expect(mockNavigate).toHaveBeenCalledTimes(destinations.length);
    expect(useQuery).toHaveBeenCalledTimes(1);
  });

  it('keeps quick actions reachable while dashboard data is loading', async () => {
    jest.mocked(useQuery).mockReturnValue({
      isError: false,
      isFetching: true,
      isPending: true,
      isRefetching: false,
      refetch: jest.fn(),
    } as unknown as ReturnType<typeof useQuery>);

    const screen = await render(<DashboardScreen />);

    expect(screen.getByText('Quick Actions')).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: 'Customers' }));

    expect(mockNavigate).toHaveBeenCalledWith('/customers');
  });
});

function collectText(node: unknown): string[] {
  if (typeof node === 'string') return [node];
  if (!node || typeof node !== 'object') return [];
  if (Array.isArray(node)) return node.flatMap(collectText);
  if ('children' in node) return collectText(node.children);
  return [];
}
