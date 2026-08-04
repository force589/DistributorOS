import { type Href, usePathname, useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { appIcons, type AppIconName } from '@/design/icons';
import { BottomNavigation } from '@/design-system';
import {
  getActivePrimaryNavigationKey,
  primaryRoutes,
  shouldNavigateToPrimaryRoute,
  type PrimaryNavigationKey,
} from '@/navigation/primaryNavigation';

const items: { key: PrimaryNavigationKey; icon: AppIconName; translationKey: string }[] = [
  { key: 'home', icon: appIcons.home, translationKey: 'navigation.home' },
  { key: 'sales', icon: appIcons.sales, translationKey: 'navigation.sales' },
  { key: 'customers', icon: appIcons.customers, translationKey: 'navigation.customers' },
  { key: 'products', icon: appIcons.products, translationKey: 'navigation.products' },
  { key: 'more', icon: appIcons.more, translationKey: 'navigation.more' },
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
