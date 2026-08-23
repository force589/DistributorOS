import type { StockMovement } from '@distributoros/api-client';
import { keepPreviousData, useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useIsFocused, useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
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
import { HeadingText } from '@/design-system';
import { getInventoryErrorTranslationKey } from '@/features/inventory/errorMessages';
import {
  formatInventoryDate,
  formatStockQuantity,
  movementTypeKeys,
} from '@/features/inventory/formatting';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

export default function InventoryHistoryScreen() {
  const { t, i18n } = useTranslation();
  const isFocused = useIsFocused();
  const router = useRouter();
  const params = useLocalSearchParams<{ productCode?: string }>();
  const productCode = Array.isArray(params.productCode)
    ? params.productCode[0]
    : params.productCode;
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const loadingMore = useRef(false);
  const productQuery = useQuery({
    queryKey: ['product', productCode],
    queryFn: ({ signal }) => apiClient.getProductByCode(productCode!, signal),
    enabled: Boolean(productCode),
    subscribed: isFocused,
  });
  const query = useInfiniteQuery({
    queryKey: ['inventory', 'history', productQuery.data?.id ?? null, debouncedSearch],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) =>
      apiClient.inventoryHistory(
        {
          productId: productQuery.data?.id,
          search: debouncedSearch || undefined,
          cursor: pageParam,
          limit: 25,
        },
        signal,
      ),
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    placeholderData: keepPreviousData,
    enabled: !productCode || Boolean(productQuery.data),
    subscribed: isFocused,
  });
  const movements = useMemo(
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

  if ((productCode && productQuery.isPending) || query.isPending) {
    return (
      <FullScreenState
        loading
        message={t('inventory.history.loadingMessage')}
        title={t('inventory.history.loadingTitle')}
      />
    );
  }
  if (productQuery.isError || (query.isError && movements.length === 0)) {
    return (
      <FullScreenState
        actionLabel={t('common.back')}
        message={t('inventory.history.errorMessage')}
        onAction={() => router.replace('/inventory')}
        title={t('inventory.history.errorTitle')}
      />
    );
  }
  const emptyTitle = debouncedSearch
    ? t('inventory.history.noResultsTitle')
    : t('inventory.history.emptyTitle');
  const emptyMessage = debouncedSearch
    ? t('inventory.history.noResultsMessage')
    : t('inventory.history.emptyMessage');

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => productCode
          ? router.push(`/inventory/${productCode}`)
          : router.push('/inventory')}
        subtitle={t('inventory.history.subtitle')}
        title={productQuery.data?.name ?? t('inventory.history.title')}
      />
      <View style={styles.controls}>
        <TextInput
          accessibilityLabel={t('inventory.history.searchLabel')}
          autoCapitalize="none"
          onChangeText={setSearch}
          placeholder={t('inventory.history.searchPlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.search}
          value={search}
        />
        {query.isFetching && !query.isFetchingNextPage ? (
          <View style={styles.updating}>
            <ActivityIndicator color={colors.primary} size="small" />
            <Text style={styles.muted}>{t('inventory.history.updating')}</Text>
          </View>
        ) : null}
      </View>
      {query.isRefetchError ? (
        <View style={styles.inlineError}>
          <FeedbackBanner message={t(getInventoryErrorTranslationKey(query.error))} />
        </View>
      ) : null}
      <FlatList
        contentContainerStyle={movements.length ? styles.list : styles.emptyList}
        data={movements}
        keyExtractor={(item) => item.id}
        ListEmptyComponent={
          <View style={styles.empty}>
            <HeadingText level={2} style={styles.emptyTitle}>{emptyTitle}</HeadingText>
            <Text style={styles.emptyMessage}>{emptyMessage}</Text>
          </View>
        }
        ListFooterComponent={query.isFetchingNextPage ? (
          <View style={styles.loadingMore}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.muted}>{t('inventory.history.loadingMore')}</Text>
          </View>
        ) : null}
        onEndReached={() => void loadMore()}
        onEndReachedThreshold={0.4}
        renderItem={({ item }) => <MovementRow item={item} language={i18n.language} />}
      />
    </SafeAreaView>
  );
}

function MovementRow({ item, language }: { item: StockMovement; language: string }) {
  const { t } = useTranslation();
  return (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <Text style={styles.productName}>{item.product_name}</Text>
        <Text style={styles.quantity}>
          {formatStockQuantity(item.quantity, item.unit, language, t)}
        </Text>
      </View>
      <Text style={styles.movementType}>{t(movementTypeKeys[item.movement_type])}</Text>
      <Text style={styles.muted}>{item.product_code}</Text>
      <Text style={styles.muted}>{formatInventoryDate(item.created_at, language)}</Text>
      <Text style={styles.meta}>
        {t('inventory.history.reference')}: {' '}
        {item.reference_type ?? t('inventory.history.noReference')}
      </Text>
      <Text style={styles.meta}>
        {t('inventory.history.remarks')}: {' '}
        {item.remarks ?? t('inventory.history.noRemarks')}
      </Text>
      <Text style={styles.meta}>
        {t('inventory.history.user')}: {item.created_by_email}
      </Text>
    </View>
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
    gap: spacing.md,
    justifyContent: 'space-between',
  },
  productName: { color: colors.text, flex: 1, fontSize: 17, fontWeight: '700' },
  quantity: { color: colors.text, fontSize: 17, fontWeight: '800' },
  movementType: { color: colors.primary, fontSize: 14, fontWeight: '700' },
  muted: { color: colors.textMuted, fontSize: 13 },
  meta: { color: colors.text, fontSize: 14, lineHeight: 20 },
});
