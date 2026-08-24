import type { SaleListItem, SaleSort, SaleStatus } from '@distributoros/api-client';
import { keepPreviousData, useInfiniteQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { apiClient } from '@/api/client';
import { FeedbackBanner } from '@/components/FeedbackBanner';
import { FullScreenState } from '@/components/FullScreenState';
import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import { FilterChipGroup, HeadingText, ListSkeleton } from '@/design-system';
import { getSaleErrorTranslationKey } from '@/features/sales/errorMessages';
import {
  formatInr,
  formatSaleDate,
  saleRowKey,
  saleStatusKeys,
} from '@/features/sales/formatting';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

const statuses: SaleStatus[] = ['all', 'draft', 'posted', 'void'];
const sorts: SaleSort[] = ['newest', 'oldest'];

function validIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value);
}

export default function SalesListScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [date, setDate] = useState('');
  const [status, setStatus] = useState<SaleStatus>('all');
  const [sort, setSort] = useState<SaleSort>('newest');
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const debouncedDate = useDebouncedValue(date.trim(), 300);
  const dateError = Boolean(debouncedDate) && !validIsoDate(debouncedDate);
  const loadingMore = useRef(false);
  const query = useInfiniteQuery({
    queryKey: ['sales', 'list', status, sort, debouncedSearch, debouncedDate],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) => apiClient.listSales({
      status,
      sort,
      search: debouncedSearch || undefined,
      date: !dateError && debouncedDate ? debouncedDate : undefined,
      limit: 25,
      cursor: pageParam,
    }, signal),
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    placeholderData: keepPreviousData,
    enabled: !dateError,
  });
  const sales = useMemo(
    () => query.data?.pages.flatMap((page) => page.items) ?? [],
    [query.data],
  );
  const loadMore = async () => {
    if (!query.hasNextPage || loadingMore.current) return;
    loadingMore.current = true;
    try {
      await query.fetchNextPage();
    } finally {
      loadingMore.current = false;
    }
  };

  if (query.isPending) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <ScreenHeader
          actionLabel={t('sales.list.create')}
          level="primary"
          onAction={() => router.push('/sales/new')}
          subtitle={t('sales.list.subtitle')}
          title={t('sales.list.title')}
        />
        <ListSkeleton
          accessibilityLabel={`${t('sales.list.loadingTitle')}. ${t('sales.list.loadingMessage')}`}
        />
      </SafeAreaView>
    );
  }
  if (query.isError && sales.length === 0) {
    return (
      <FullScreenState
        actionLabel={t('common.retry')}
        message={t('sales.list.errorMessage')}
        onAction={() => void query.refetch()}
        title={t('sales.list.errorTitle')}
      />
    );
  }
  const filtered = Boolean(debouncedSearch || debouncedDate || status !== 'all');

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        actionLabel={t('sales.list.create')}
        level="primary"
        onAction={() => router.push('/sales/new')}
        subtitle={t('sales.list.subtitle')}
        title={t('sales.list.title')}
      />
      <View style={styles.controls}>
        <TextInput
          accessibilityLabel={t('sales.list.searchLabel')}
          autoCapitalize="none"
          onChangeText={setSearch}
          placeholder={t('sales.list.searchPlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={search}
        />
        <TextInput
          accessibilityLabel={t('sales.list.dateLabel')}
          autoCapitalize="none"
          keyboardType="numbers-and-punctuation"
          maxLength={10}
          onChangeText={setDate}
          placeholder={t('sales.list.datePlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={date}
        />
        {dateError ? <Text style={styles.error}>{t('sales.validation.dateInvalid')}</Text> : null}
        <FilterChipGroup
          label={t('sales.list.filterLabel')}
          onSelect={(value) => setStatus(value as SaleStatus)}
          options={statuses.map((value) => ({
            value,
            label: value === 'all' ? t('sales.filters.all') : t(saleStatusKeys[value]),
          }))}
          selected={status}
          testIDPrefix="sale-status"
        />
        <FilterChipGroup
          label={t('sales.list.sortLabel')}
          onSelect={(value) => setSort(value as SaleSort)}
          options={sorts.map((value) => ({
            value,
            label: t(value === 'newest' ? 'sales.sorts.newest' : 'sales.sorts.oldest'),
          }))}
          selected={sort}
          testIDPrefix="sale-sort"
        />
        {query.isFetching && !query.isFetchingNextPage ? (
          <View style={styles.updating}>
            <ActivityIndicator color={colors.primary} size="small" />
            <Text style={styles.muted}>{t('sales.list.updating')}</Text>
          </View>
        ) : null}
      </View>
      {query.isRefetchError ? (
        <View style={styles.inlineError}>
          <FeedbackBanner message={t(getSaleErrorTranslationKey(query.error))} />
        </View>
      ) : null}
      <FlatList
        contentContainerStyle={sales.length ? styles.list : styles.emptyList}
        data={sales}
        keyExtractor={saleRowKey}
        ListEmptyComponent={
          <View style={styles.empty}>
            <HeadingText level={2} style={styles.emptyTitle}>
              {t(filtered ? 'sales.list.noResultsTitle' : 'sales.list.emptyTitle')}
            </HeadingText>
            <Text style={styles.emptyMessage}>
              {t(filtered ? 'sales.list.noResultsMessage' : 'sales.list.emptyMessage')}
            </Text>
          </View>
        }
        ListFooterComponent={query.isFetchingNextPage ? (
          <View style={styles.loadingMore}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.muted}>{t('sales.list.loadingMore')}</Text>
          </View>
        ) : null}
        onEndReached={() => void loadMore()}
        onEndReachedThreshold={0.4}
        renderItem={({ item }) => (
          <SaleRow
            item={item}
            language={i18n.language}
            onPress={() => router.push(`/sales/${item.sale_number}`)}
          />
        )}
      />
    </SafeAreaView>
  );
}

function SaleRow({ item, language, onPress }: {
  item: SaleListItem;
  language: string;
  onPress: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.card}>
      <View style={styles.topRow}>
        <View style={styles.identity}>
          <Text style={styles.saleNumber}>{item.sale_number}</Text>
          <Text style={styles.customer}>{item.customer_name}</Text>
        </View>
        <Text style={[styles.badge, styles[`badge${item.status}`]]}>
          {t(saleStatusKeys[item.status])}
        </Text>
      </View>
      <View style={styles.metaRow}>
        <Text style={styles.total}>{formatInr(item.subtotal, language)}</Text>
        <Text style={styles.muted}>{t('sales.list.items', { count: item.item_count })}</Text>
      </View>
      <Text style={styles.muted}>{formatSaleDate(item.created_at, language)}</Text>
    </Pressable>
  );
}

const styles = ThemedStyleSheet.create({
  safeArea: { backgroundColor: colors.background, flex: 1 },
  controls: {
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    gap: spacing.sm,
    padding: spacing.md,
  },
  input: {
    borderColor: colors.border,
    borderRadius: radii.md,
    borderWidth: 1,
    color: colors.text,
    fontSize: 16,
    minHeight: 48,
    paddingHorizontal: spacing.md,
  },
  error: { color: colors.danger, fontSize: 13 },
  updating: { alignItems: 'center', flexDirection: 'row', gap: spacing.sm },
  muted: { color: colors.textMuted, fontSize: 13 },
  inlineError: { padding: spacing.md },
  list: { gap: spacing.md, padding: spacing.md },
  emptyList: { flexGrow: 1 },
  empty: {
    alignItems: 'center',
    flex: 1,
    gap: spacing.md,
    justifyContent: 'center',
    padding: spacing.xl,
  },
  emptyTitle: { color: colors.text, fontSize: 22, fontWeight: '700', textAlign: 'center' },
  emptyMessage: { color: colors.textMuted, fontSize: 15, lineHeight: 22, textAlign: 'center' },
  loadingMore: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'center',
    padding: spacing.lg,
  },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.md,
    borderWidth: 1,
    gap: spacing.sm,
    padding: spacing.md,
  },
  topRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'space-between',
  },
  identity: { flex: 1, gap: spacing.xs },
  saleNumber: { color: colors.primary, fontSize: 14, fontWeight: '800' },
  customer: { color: colors.text, fontSize: 18, fontWeight: '700' },
  badge: {
    borderRadius: 999,
    fontSize: 12,
    fontWeight: '800',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  badgeDRAFT: { backgroundColor: colors.warningBackground, color: colors.warning },
  badgePOSTED: { backgroundColor: colors.successBackground, color: colors.success },
  badgeVOID: { backgroundColor: colors.dangerBackground, color: colors.danger },
  metaRow: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  total: { color: colors.text, fontSize: 17, fontWeight: '800' },
});
