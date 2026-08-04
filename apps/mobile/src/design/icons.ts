import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import type { ComponentProps } from 'react';

export type AppIconName = ComponentProps<typeof MaterialCommunityIcons>['name'];

export const appIcons = {
  account: 'account-circle-outline',
  appearance: 'theme-light-dark',
  business: 'office-building-outline',
  chevronRight: 'chevron-right',
  customers: 'account-group-outline',
  home: 'home-outline',
  inventory: 'warehouse',
  invoices: 'receipt-text-outline',
  language: 'translate',
  more: 'menu',
  payments: 'credit-card-outline',
  products: 'package-variant-closed',
  reports: 'chart-box-outline',
  sales: 'cash-register',
  search: 'magnify',
  settings: 'cog-outline',
} as const satisfies Record<string, AppIconName>;
