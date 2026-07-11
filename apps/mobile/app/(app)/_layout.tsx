import { type Href, Stack, usePathname, useRouter } from 'expo-router';
import { View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { AppBottomNavigation } from '@/components/AppBottomNavigation';
import { SettingsButton } from '@/components/SettingsButton';
import { useTheme } from '@/design/theme';
import { UnsavedChangesProvider, useUnsavedChanges } from '@/navigation/UnsavedChangesContext';

export default function AppLayout() {
  return (
    <UnsavedChangesProvider>
      <AppLayoutContent />
    </UnsavedChangesProvider>
  );
}

function AppLayoutContent() {
  const { t } = useTranslation();
  const pathname = usePathname();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const theme = useTheme();
  const { guardNavigation } = useUnsavedChanges();
  const isSettings = pathname === '/settings';

  return (
    <View style={{ backgroundColor: theme.colors.background, flex: 1 }}>
      <View style={{ flex: 1 }}>
        <Stack screenOptions={{ headerShown: false }} />
      </View>
      <AppBottomNavigation bottomInset={insets.bottom} onNavigate={guardNavigation} />
      {!isSettings ? (
        <View
          style={{
            pointerEvents: 'box-none',
            position: 'absolute',
            right: theme.spacing.md,
            top: Math.max(insets.top, theme.spacing.sm) + theme.spacing.sm,
            zIndex: 100,
          }}
        >
          <SettingsButton
            hint={t('settings.openHint')}
            label={t('settings.open')}
            onPress={() => guardNavigation(() => router.push('/settings' as Href))}
          />
        </View>
      ) : null}
    </View>
  );
}
