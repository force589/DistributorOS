import { type Href, usePathname, useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { BottomNavigation } from '@/design-system';
import {
  getActivePrimaryNavigationKey,
  primaryRoutes,
  shouldNavigateToPrimaryRoute,
  type PrimaryNavigationKey,
} from '@/navigation/primaryNavigation';

const items: { key: PrimaryNavigationKey; icon: string; translationKey: string }[] = [
  { key: 'home', icon: '🏠', translationKey: 'navigation.home' },
  { key: 'sales', icon: '💰', translationKey: 'navigation.sales' },
  { key: 'customers', icon: '👥', translationKey: 'navigation.customers' },
  { key: 'products', icon: '📦', translationKey: 'navigation.products' },
  { key: 'more', icon: '☰', translationKey: 'navigation.more' },
];

export function AppBottomNavigation({
  bottomInset = 0,
  onNavigate = (action) => action(),
}: {
  bottomInset?: number;
  onNavigate?: (action: () => void) => void;
}) {
  const { t } = useTranslation();
  const pathname = usePathname();
  const router = useRouter();
  const activeKey = getActivePrimaryNavigationKey(pathname);

  return (
    <BottomNavigation
      bottomInset={bottomInset}
      items={items.map((item) => ({
        icon: item.icon,
        key: item.key,
        label: t(item.translationKey),
        onPress: () => {
          const target = primaryRoutes[item.key];
          if (shouldNavigateToPrimaryRoute(pathname, target)) {
            onNavigate(() => router.navigate(target as Href));
          }
        },
        selected: activeKey === item.key,
      }))}
    />
  );
}
