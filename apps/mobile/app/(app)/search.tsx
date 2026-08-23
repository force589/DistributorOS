import type { GlobalSearchItem, GlobalSearchResult } from '@distributoros/api-client';
import { useQuery } from '@tanstack/react-query';
import { type Href, useRouter } from 'expo-router';
import type { TFunction } from 'i18next';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { apiClient } from '@/api/client';
import { FeedbackBanner } from '@/components/FeedbackBanner';
import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import { HeadingText } from '@/design-system';
import { getInsightsErrorTranslationKey } from '@/features/insights/errorMessages';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

type SearchGroupKey = keyof Pick<
  GlobalSearchResult,
  'customers' | 'products' | 'sales' | 'invoices' | 'payments' | 'inventory'
>;

const groups: SearchGroupKey[] = [
  'customers',
  'products',
  'invoices',
  'sales',
  'payments',
  'inventory',
];

export default function GlobalSearchScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const [queryText, setQueryText] = useState('');
  const debounced = useDebouncedValue(queryText.trim(), 300);

  const search = useQuery({
    enabled: debounced.length > 0,
    queryFn: ({ signal }) => apiClient.globalSearch(debounced, { limitPerGroup: 5 }, signal),
    queryKey: ['global-search', debounced],
  });

  const hasResults = groups.some((group) => (search.data?.[group] ?? []).length > 0);

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo('/(app)')}
        subtitle={t('insights.search.subtitle')}
        title={t('insights.search.title')}
      />
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <TextInput
          accessibilityLabel={t('insights.search.label')}
          autoCapitalize="none"
          onChangeText={setQueryText}
          placeholder={t('insights.search.placeholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.searchInput}
          value={queryText}
        />
        {search.isFetching ? (
          <View style={styles.inlineState}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.muted}>{t('insights.search.loading')}</Text>
          </View>
        ) : null}
        {search.isError ? (
          <FeedbackBanner message={t(getInsightsErrorTranslationKey(search.error, 'search'))} />
        ) : null}
        {!debounced ? (
          <View style={styles.empty}>
            <HeadingText level={2} style={styles.emptyTitle}>
              {t('insights.search.startTitle')}
            </HeadingText>
            <Text style={styles.emptyMessage}>{t('insights.search.startMessage')}</Text>
          </View>
        ) : null}
        {debounced && search.isSuccess && !hasResults ? (
          <View style={styles.empty}>
            <HeadingText level={2} style={styles.emptyTitle}>
              {t('insights.search.emptyTitle')}
            </HeadingText>
            <Text style={styles.emptyMessage}>{t('insights.search.emptyMessage')}</Text>
          </View>
        ) : null}
        {search.data ? (
          groups.map((group) => (
            <View key={group} style={styles.section}>
              <HeadingText level={2} style={styles.sectionTitle}>
                {t(`insights.search.groups.${group}`)}
              </HeadingText>
              {search.data[group].length ? search.data[group].map((item) => (
                <Pressable
                  accessibilityRole="button"
                  key={`${item.type}-${item.id}`}
                  onPress={() => router.push(item.detail_path as Href)}
                  style={styles.result}
                >
                  <View style={styles.resultText}>
                    <Text style={styles.resultTitle}>{item.title}</Text>
                    {item.subtitle ? (
                      <Text style={styles.resultSubtitle}>{item.subtitle}</Text>
                    ) : null}
                  </View>
                  <Text style={styles.reference}>{referenceLabel(item, t)}</Text>
                </Pressable>
              )) : <Text style={styles.muted}>{t('insights.search.noGroupResults')}</Text>}
            </View>
          ))
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

function referenceLabel(
  item: GlobalSearchItem,
  t: TFunction,
): string {
  if (item.type === 'sale') return t(`sales.status.${camelStatus(item.reference)}`);
  if (item.type === 'invoice') return t(`invoices.status.${camelStatus(item.reference)}`);
  if (item.type === 'payment') return t(`payments.status.${camelStatus(item.reference)}`);
  return item.reference;
}

function camelStatus(value: string): string {
  return value.toLowerCase().replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
}

const styles = ThemedStyleSheet.create({
  safeArea: {
    backgroundColor: colors.background,
    flex: 1,
  },
  content: {
    gap: spacing.md,
    padding: spacing.lg,
  },
  searchInput: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.md,
    borderWidth: 1,
    color: colors.text,
    fontSize: 16,
    minHeight: 52,
    paddingHorizontal: spacing.md,
  },
  inlineState: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.sm,
  },
  empty: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.lg,
    borderWidth: 1,
    gap: spacing.sm,
    padding: spacing.lg,
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  emptyMessage: {
    color: colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
  },
  section: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.lg,
    borderWidth: 1,
    gap: spacing.sm,
    padding: spacing.md,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '800',
  },
  result: {
    alignItems: 'center',
    borderTopColor: colors.border,
    borderTopWidth: 1,
    flexDirection: 'row',
    gap: spacing.md,
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
  },
  resultText: {
    flex: 1,
    gap: spacing.xs,
  },
  resultTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  resultSubtitle: {
    color: colors.textMuted,
    fontSize: 13,
  },
  reference: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '800',
  },
  muted: {
    color: colors.textMuted,
    fontSize: 14,
  },
});
