import type { Product, ProductSort, ProductStatus } from '@distributoros/api-client';
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
import { PrimaryButton } from '@/components/PrimaryButton';
import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import { FilterChipGroup, HeadingText, ListSkeleton } from '@/design-system';
import { getProductErrorTranslationKey } from '@/features/products/errorMessages';
import { formatInr, productUnitKeys } from '@/features/products/formatting';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

const statuses: ProductStatus[] = ['all', 'active', 'archived'];
const sorts: ProductSort[] = [
  'newest',
  'oldest',
  'name_asc',
  'name_desc',
  'price_asc',
  'price_desc',
];

export default function ProductListScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<ProductStatus>('active');
  const [sort, setSort] = useState<ProductSort>('newest');
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const loadingMore = useRef(false);
  const query = useInfiniteQuery({
    queryKey: ['products', status, sort, debouncedSearch],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) =>
      apiClient.listProducts(
        {
          status,
          sort,
          search: debouncedSearch || undefined,
          cursor: pageParam,
          limit: 25,
        },
        signal,
      ),
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    placeholderData: keepPreviousData,
  });
  const products = useMemo(
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
          actionLabel={t('products.list.create')}
          level="primary"
          onAction={() => router.push('/products/new')}
          subtitle={t('products.list.subtitle')}
          title={t('products.list.title')}
        />
        <ListSkeleton
          accessibilityLabel={`${t('products.list.loadingTitle')}. ${t('products.list.loadingMessage')}`}
        />
      </SafeAreaView>
    );
  }
  if (query.isError && products.length === 0) {
    return (
      <FullScreenState
        actionLabel={t('common.retry')}
        message={t('products.list.errorMessage')}
        onAction={() => void query.refetch()}
        title={t('products.list.errorTitle')}
      />
    );
  }

  const emptyTitle = debouncedSearch
    ? t('products.list.noResultsTitle')
    : status === 'archived'
      ? t('products.list.noArchivedTitle')
      : t('products.list.emptyTitle');
  const emptyMessage = debouncedSearch
    ? t('products.list.noResultsMessage')
    : status === 'archived'
      ? t('products.list.noArchivedMessage')
      : t('products.list.emptyMessage');

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        actionLabel={t('products.list.create')}
        level="primary"
        onAction={() => router.push('/products/new')}
        subtitle={t('products.list.subtitle')}
        title={t('products.list.title')}
      />
      <View style={styles.controls}>
        <TextInput
          accessibilityLabel={t('products.list.searchLabel')}
          autoCapitalize="none"
          onChangeText={setSearch}
          placeholder={t('products.list.searchPlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.search}
          value={search}
        />
        {query.isFetching && !query.isFetchingNextPage ? (
          <View style={styles.updating}>
            <ActivityIndicator color={colors.primary} size="small" />
            <Text style={styles.mutedText}>{t('products.list.updating')}</Text>
          </View>
        ) : null}
        <FilterChipGroup
          label={t('products.list.filterLabel')}
          onSelect={(value) => setStatus(value as ProductStatus)}
          options={statuses.map((option) => ({
            label: option === 'all'
              ? t('products.filters.all')
              : option === 'active'
                ? t('products.filters.active')
                : t('products.filters.archived'),
            value: option,
          }))}
          selected={status}
          testIDPrefix="product-status"
        />
        <FilterChipGroup
          label={t('products.list.sortLabel')}
          onSelect={(value) => setSort(value as ProductSort)}
          options={sorts.map((option) => ({
            label: t(
              {
                newest: 'products.sorts.newest',
                oldest: 'products.sorts.oldest',
                name_asc: 'products.sorts.nameAsc',
                name_desc: 'products.sorts.nameDesc',
                price_asc: 'products.sorts.priceAsc',
                price_desc: 'products.sorts.priceDesc',
              }[option],
            ),
            value: option,
          }))}
          selected={sort}
          testIDPrefix="product-sort"
        />
      </View>
      {query.isFetchNextPageError ? (
        <InlineError
          message={t(getProductErrorTranslationKey(query.error))}
          onRetry={() => void loadMore()}
        />
      ) : null}
      {query.isRefetchError && !query.isFetchNextPageError ? (
        <InlineError
          message={t(getProductErrorTranslationKey(query.error))}
          onRetry={() => void query.refetch()}
        />
      ) : null}
      <FlatList
        contentContainerStyle={products.length ? styles.list : styles.emptyList}
        data={products}
        keyExtractor={(product) => product.product_code}
        ListEmptyComponent={
          <View style={styles.empty}>
            <HeadingText level={2} style={styles.emptyTitle}>
              {emptyTitle}
            </HeadingText>
            <Text style={styles.emptyMessage}>{emptyMessage}</Text>
            {!debouncedSearch && status !== 'archived' ? (
              <PrimaryButton
                label={t('products.list.create')}
                onPress={() => router.push('/products/new')}
              />
            ) : null}
          </View>
        }
        ListFooterComponent={
          query.isFetchingNextPage ? (
            <View style={styles.loadingMore}>
              <ActivityIndicator color={colors.primary} />
              <Text style={styles.mutedText}>{t('products.list.loadingMore')}</Text>
            </View>
          ) : null
        }
        onEndReached={() => void loadMore()}
        onEndReachedThreshold={0.4}
        renderItem={({ item }) => (
          <ProductRow
            language={i18n.language}
            onPress={() => router.push(`/products/${item.product_code}`)}
            product={item}
          />
        )}
      />
    </SafeAreaView>
  );
}

function InlineError({ message, onRetry }: { message: string; onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <View style={styles.inlineError}>
      <FeedbackBanner message={message} />
      <PrimaryButton label={t('common.retry')} onPress={onRetry} />
    </View>
  );
}

function ProductRow({
  product,
  language,
  onPress,
}: {
  product: Product;
  language: string;
  onPress: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.productCard}>
      <View style={styles.productTopRow}>
        <Text style={styles.productName}>{product.name}</Text>
        {product.archived ? (
          <Text style={styles.archivedBadge}>{t('products.list.archivedBadge')}</Text>
        ) : null}
      </View>
      <Text style={styles.productCode}>{product.product_code}</Text>
      <Text style={styles.price}>
        {formatInr(product.selling_price, language)} · {t(productUnitKeys[product.unit])}
      </Text>
      {product.category ? <Text style={styles.mutedText}>{product.category}</Text> : null}
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
  inlineError: { gap: spacing.sm, padding: spacing.md },
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
  mutedText: { color: colors.textMuted, fontSize: 14 },
  productCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.md,
    borderWidth: 1,
    gap: spacing.xs,
    padding: spacing.md,
  },
  productTopRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'space-between',
  },
  productName: { color: colors.text, flex: 1, fontSize: 18, fontWeight: '700' },
  productCode: { color: colors.primary, fontSize: 13, fontWeight: '700' },
  price: { color: colors.text, fontSize: 15, fontWeight: '700' },
  archivedBadge: {
    backgroundColor: colors.warningBackground,
    borderRadius: 999,
    color: colors.warning,
    fontSize: 12,
    fontWeight: '700',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
});
