import type { StockItem } from '@distributoros/api-client';
import { keepPreviousData, useInfiniteQuery } from '@tanstack/react-query';
import { useIsFocused, useRouter } from 'expo-router';
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
import { HeadingText, ListSkeleton } from '@/design-system';
import { getInventoryErrorTranslationKey } from '@/features/inventory/errorMessages';
import {
  formatStockQuantity,
  lowStockStatusKeys,
} from '@/features/inventory/formatting';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

export default function InventoryListScreen() {
  const { t, i18n } = useTranslation();
  const isFocused = useIsFocused();
  const router = useRouter();
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const loadingMore = useRef(false);
  const query = useInfiniteQuery({
    queryKey: ['inventory', 'stock', debouncedSearch],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) =>
      apiClient.listStock(
        { search: debouncedSearch || undefined, cursor: pageParam, limit: 25 },
        signal,
      ),
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    placeholderData: keepPreviousData,
    subscribed: isFocused,
  });
  const stock = useMemo(
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
          actionLabel={t('inventory.list.history')}
          level="primary"
          onAction={() => router.push('/inventory/history')}
          subtitle={t('inventory.list.subtitle')}
          title={t('inventory.list.title')}
        />
        <ListSkeleton
          accessibilityLabel={`${t('inventory.list.loadingTitle')}. ${t('inventory.list.loadingMessage')}`}
        />
      </SafeAreaView>
    );
  }
  if (query.isError && stock.length === 0) {
    return (
      <FullScreenState
        actionLabel={t('common.retry')}
        message={t('inventory.list.errorMessage')}
        onAction={() => void query.refetch()}
        title={t('inventory.list.errorTitle')}
      />
    );
  }
  const emptyTitle = debouncedSearch
    ? t('inventory.list.noResultsTitle')
    : t('inventory.list.emptyTitle');
  const emptyMessage = debouncedSearch
    ? t('inventory.list.noResultsMessage')
    : t('inventory.list.emptyMessage');

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        actionLabel={t('inventory.list.history')}
        level="primary"
        onAction={() => router.push('/inventory/history')}
        subtitle={t('inventory.list.subtitle')}
        title={t('inventory.list.title')}
      />
      <View style={styles.controls}>
        <TextInput
          accessibilityLabel={t('inventory.list.searchLabel')}
          autoCapitalize="none"
          onChangeText={setSearch}
          placeholder={t('inventory.list.searchPlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.search}
          value={search}
        />
        {query.isFetching && !query.isFetchingNextPage ? (
          <View style={styles.updating}>
            <ActivityIndicator color={colors.primary} size="small" />
            <Text style={styles.muted}>{t('inventory.list.updating')}</Text>
          </View>
        ) : null}
      </View>
      {query.isRefetchError ? (
        <View style={styles.inlineError}>
          <FeedbackBanner message={t(getInventoryErrorTranslationKey(query.error))} />
        </View>
      ) : null}
      <FlatList
        contentContainerStyle={stock.length ? styles.list : styles.emptyList}
        data={stock}
        keyExtractor={(item) => item.product_code}
        ListEmptyComponent={
          <View style={styles.empty}>
            <HeadingText level={2} style={styles.emptyTitle}>{emptyTitle}</HeadingText>
            <Text style={styles.emptyMessage}>{emptyMessage}</Text>
          </View>
        }
        ListFooterComponent={
          query.isFetchingNextPage ? (
            <View style={styles.loadingMore}>
              <ActivityIndicator color={colors.primary} />
              <Text style={styles.muted}>{t('inventory.list.loadingMore')}</Text>
            </View>
          ) : null
        }
        onEndReached={() => void loadMore()}
        onEndReachedThreshold={0.4}
        renderItem={({ item }) => (
          <StockRow
            item={item}
            language={i18n.language}
            onPress={() => router.push(`/inventory/${item.product_code}`)}
          />
        )}
      />
    </SafeAreaView>
  );
}

function StockRow({ item, language, onPress }: {
  item: StockItem;
  language: string;
  onPress: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.card}>
      <View style={styles.topRow}>
        <Text style={styles.productName}>{item.product_name}</Text>
        <Text style={[
          styles.status,
          item.low_stock_status === 'NORMAL'
            ? styles.normal
            : item.low_stock_status === 'LOW_STOCK'
              ? styles.low
              : styles.out,
        ]}>
          {t(lowStockStatusKeys[item.low_stock_status])}
        </Text>
      </View>
      <Text style={styles.productCode}>{item.product_code}</Text>
      <Text style={styles.quantity}>
        {t('inventory.list.available')}: {' '}
        {formatStockQuantity(item.available_quantity, item.unit, language, t)}
      </Text>
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
  search: {
    borderColor: colors.border,
    borderRadius: radii.md,
    borderWidth: 1,
    color: colors.text,
    fontSize: 16,
    minHeight: 48,
    paddingHorizontal: spacing.md,
  },
  updating: { alignItems: 'center', flexDirection: 'row', gap: spacing.sm },
  muted: { color: colors.textMuted, fontSize: 14 },
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
    gap: spacing.xs,
    padding: spacing.md,
  },
  topRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'space-between',
  },
  productName: { color: colors.text, flex: 1, fontSize: 18, fontWeight: '700' },
  productCode: { color: colors.primary, fontSize: 13, fontWeight: '700' },
  quantity: { color: colors.text, fontSize: 16, fontWeight: '700' },
  status: {
    borderRadius: 999,
    fontSize: 12,
    fontWeight: '700',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  normal: { backgroundColor: colors.successBackground, color: colors.success },
  low: { backgroundColor: colors.warningBackground, color: colors.warning },
  out: { backgroundColor: colors.dangerBackground, color: colors.danger },
});
