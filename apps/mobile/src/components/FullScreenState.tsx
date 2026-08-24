import { ActivityIndicator, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { useTheme } from '@/design/theme';
import { Card, ErrorState, HeadingText, LoadingState, SkeletonCardGrid } from '@/design-system';

interface FullScreenStateProps {
  title: string;
  message: string;
  loading?: boolean;
  actionLabel?: string;
  onAction?: () => void;
}

export function FullScreenState({ title, message, loading = false, actionLabel, onAction }: FullScreenStateProps) {
  const theme = useTheme();
  return (
    <SafeAreaView style={{ backgroundColor: theme.colors.background, flex: 1, justifyContent: 'center' }}>
      {loading ? <LoadingState message={message} title={title} /> : <ErrorState message={message} onRetry={onAction} retryLabel={actionLabel} title={title} />}
    </SafeAreaView>
  );
}

export function SessionRestoreShell({ title, message }: Pick<FullScreenStateProps, 'title' | 'message'>) {
  const theme = useTheme();
  const { t } = useTranslation();
  return (
    <SafeAreaView style={{ backgroundColor: theme.colors.background, flex: 1 }}>
      <View
        style={{
          backgroundColor: theme.colors.surface,
          borderBottomColor: theme.colors.border,
          borderBottomWidth: 1,
          gap: theme.spacing.xs,
          paddingHorizontal: theme.spacing.lg,
          paddingVertical: theme.spacing.md,
        }}
      >
        <HeadingText
          level={1}
          style={[theme.typography.title, { color: theme.colors.primary }]}
        >
          {t('brand.name')}
        </HeadingText>
        <Text style={[theme.typography.caption, { color: theme.colors.textMuted }]}>
          {t('brand.tagline')}
        </Text>
      </View>
      <View
        style={{
          gap: theme.spacing.lg,
          padding: theme.spacing.lg,
        }}
      >
        <Card style={{ gap: theme.spacing.sm }}>
          <View style={{ alignItems: 'center', flexDirection: 'row', gap: theme.spacing.md }}>
            <ActivityIndicator color={theme.colors.primary} />
            <View style={{ flex: 1, gap: theme.spacing.xs }}>
              <HeadingText
                level={2}
                style={[theme.typography.heading, { color: theme.colors.text }]}
              >
                {title}
              </HeadingText>
              <Text style={[theme.typography.body, { color: theme.colors.textMuted }]}>
                {message}
              </Text>
            </View>
          </View>
        </Card>
        <SkeletonCardGrid cards={6} columns={2} />
      </View>
    </SafeAreaView>
  );
}
