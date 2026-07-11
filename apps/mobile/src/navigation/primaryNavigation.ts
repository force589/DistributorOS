export type PrimaryNavigationKey = 'home' | 'sales' | 'customers' | 'products' | 'more';

export const primaryRoutes: Record<PrimaryNavigationKey, string> = {
  home: '/',
  sales: '/sales',
  customers: '/customers',
  products: '/products',
  more: '/more',
};

export function getActivePrimaryNavigationKey(pathname: string): PrimaryNavigationKey {
  if (pathname === '/') return 'home';
  if (pathname === '/sales' || pathname.startsWith('/sales/')) return 'sales';
  if (pathname === '/customers' || pathname.startsWith('/customers/')) return 'customers';
  if (pathname === '/products' || pathname.startsWith('/products/')) return 'products';
  return 'more';
}

export function shouldNavigateToPrimaryRoute(pathname: string, target: string): boolean {
  return pathname !== target;
}
