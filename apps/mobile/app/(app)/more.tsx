import { type Href, useRouter } from 'expo-router';
import { Fragment } from 'react';
import { ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { ScreenHeader } from '@/components/ScreenHeader';
import { appIcons, type AppIconName } from '@/design/icons';
import { useResponsiveLayout } from '@/design/responsive';
import { useTheme } from '@/design/theme';
import { Card, Divider, NavigationListItem } from '@/design-system';

const destinations: { key: string; icon: AppIconName; href: Href }[] = [
  { key: 'inventory', icon: appIcons.inventory, href: '/inventory' },
  { key: 'payments', icon: appIcons.payments, href: '/payments' },
  { key: 'invoices', icon: appIcons.invoices, href: '/invoices' },
  { key: 'reports', icon: appIcons.reports, href: '/reports' },
  { key: 'search', icon: appIcons.search, href: '/search' },
  { key: 'settings', icon: appIcons.settings, href: '/settings' },
];

export default function MoreScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const responsive = useResponsiveLayout();
  const theme = useTheme();

  return (
    <SafeAreaView style={{ backgroundColor: theme.colors.background, flex: 1 }}>
      <ScreenHeader level="primary" subtitle={t('more.subtitle')} title={t('more.title')} />
      <ScrollView
        contentContainerStyle={{
          alignItems: 'center',
          paddingBottom: theme.spacing.xxxl,
          paddingHorizontal: responsive.isPhone ? theme.spacing.md : theme.spacing.lg,
          paddingTop: theme.spacing.lg,
        }}
      >
        <View style={{ maxWidth: 760, width: '100%' }}>
          <Card style={{ overflow: 'hidden', padding: theme.spacing.sm }}>
            {destinations.map((destination, index) => (
              <Fragment key={destination.key}>
                <NavigationListItem
                  icon={destination.icon}
                  onPress={() => router.navigate(destination.href as Href)}
                  subtitle={t(`more.items.${destination.key}.subtitle`)}
                  testID={`more-${destination.key}`}
                  title={t(`more.items.${destination.key}.title`)}
                />
                {index < destinations.length - 1 ? <Divider /> : null}
              </Fragment>
            ))}
          </Card>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
