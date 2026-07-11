import type { PropsWithChildren } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { useTheme } from '@/design/theme';
import { Card } from '@/design-system';

interface AuthScreenLayoutProps extends PropsWithChildren {
  title: string;
  subtitle: string;
}

export function AuthScreenLayout({ title, subtitle, children }: AuthScreenLayoutProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <SafeAreaView style={{ backgroundColor: theme.colors.background, flex: 1 }}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ alignSelf: 'center', flexGrow: 1, justifyContent: 'center', maxWidth: 560, padding: theme.spacing.lg, width: '100%' }} keyboardShouldPersistTaps="handled">
          <View style={{ alignItems: 'center', gap: theme.spacing.xs, marginBottom: theme.spacing.xl }}>
            <Text style={[theme.typography.title, { color: theme.colors.primary }]}>{t('brand.name')}</Text>
            <Text style={[theme.typography.label, { color: theme.colors.textMuted, textAlign: 'center' }]}>{t('brand.tagline')}</Text>
          </View>
          <Card style={{ gap: theme.spacing.lg }}>
            <View style={{ gap: theme.spacing.sm }}>
              <Text accessibilityRole="header" style={[theme.typography.title, { color: theme.colors.text }]}>{title}</Text>
              <Text style={[theme.typography.body, { color: theme.colors.textMuted }]}>{subtitle}</Text>
            </View>
            {children}
          </Card>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
