import type { Customer, CustomerSort, CustomerStatus } from '@distributoros/api-client';
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
import { getCustomerErrorTranslationKey } from '@/features/customers/errorMessages';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

const statuses: CustomerStatus[] = ['all', 'active', 'archived'];
const sorts: CustomerSort[] = ['newest', 'oldest', 'name_asc', 'name_desc'];

export default function CustomerListScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<CustomerStatus>('active');
  const [sort, setSort] = useState<CustomerSort>('newest');
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const loadingMore = useRef(false);

  const query = useInfiniteQuery({
    queryKey: ['customers', status, sort, debouncedSearch],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) =>
      apiClient.listCustomers(
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

  const customers = useMemo(
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
          actionLabel={t('customers.list.create')}
          level="primary"
          onAction={() => router.push('/customers/new')}
          subtitle={t('customers.list.subtitle')}
          title={t('customers.list.title')}
        />
        <ListSkeleton
          accessibilityLabel={`${t('customers.list.loadingTitle')}. ${t('customers.list.loadingMessage')}`}
        />
      </SafeAreaView>
    );
  }
  if (query.isError && customers.length === 0) {
    return (
      <FullScreenState
        actionLabel={t('common.retry')}
        message={t('customers.list.errorMessage')}
        onAction={() => void query.refetch()}
        title={t('customers.list.errorTitle')}
      />
    );
  }

  const emptyTitle = debouncedSearch
    ? t('customers.list.noResultsTitle')
    : status === 'archived'
      ? t('customers.list.noArchivedTitle')
      : t('customers.list.emptyTitle');
  const emptyMessage = debouncedSearch
    ? t('customers.list.noResultsMessage')
    : status === 'archived'
      ? t('customers.list.noArchivedMessage')
      : t('customers.list.emptyMessage');

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        actionLabel={t('customers.list.create')}
        level="primary"
        onAction={() => router.push('/customers/new')}
        subtitle={t('customers.list.subtitle')}
        title={t('customers.list.title')}
      />
      <View style={styles.controls}>
        <TextInput
          accessibilityLabel={t('customers.list.searchLabel')}
          autoCapitalize="none"
          onChangeText={setSearch}
          placeholder={t('customers.list.searchPlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.search}
          value={search}
        />
        {query.isFetching && !query.isFetchingNextPage ? (
          <View style={styles.updating}>
            <ActivityIndicator color={colors.primary} size="small" />
            <Text style={styles.loadingMoreText}>{t('customers.list.updating')}</Text>
          </View>
        ) : null}
        <FilterChipGroup
          label={t('customers.list.filterLabel')}
          onSelect={(value) => setStatus(value as CustomerStatus)}
          options={statuses.map((option) => ({
            label: option === 'all'
              ? t('customers.filters.all')
              : option === 'active'
                ? t('customers.filters.active')
                : t('customers.filters.archived'),
            value: option,
          }))}
          selected={status}
          testIDPrefix="customer-status"
        />
        <FilterChipGroup
          label={t('customers.list.sortLabel')}
          onSelect={(value) => setSort(value as CustomerSort)}
          options={sorts.map((option) => ({
            label: option === 'newest'
              ? t('customers.sorts.newest')
              : option === 'oldest'
                ? t('customers.sorts.oldest')
                : option === 'name_asc'
                  ? t('customers.sorts.nameAsc')
                  : t('customers.sorts.nameDesc'),
            value: option,
          }))}
          selected={sort}
          testIDPrefix="customer-sort"
        />
      </View>
      {query.isFetchNextPageError ? (
        <View style={styles.inlineError}>
          <FeedbackBanner message={t(getCustomerErrorTranslationKey(query.error))} />
          <PrimaryButton label={t('common.retry')} onPress={() => void loadMore()} />
        </View>
      ) : null}
      {query.isRefetchError && !query.isFetchNextPageError ? (
        <View style={styles.inlineError}>
          <FeedbackBanner message={t(getCustomerErrorTranslationKey(query.error))} />
          <PrimaryButton label={t('common.retry')} onPress={() => void query.refetch()} />
        </View>
      ) : null}
      <FlatList
        contentContainerStyle={customers.length ? styles.list : styles.emptyList}
        data={customers}
        keyExtractor={(customer) => customer.customer_code}
        ListEmptyComponent={
          <View style={styles.empty}>
            <HeadingText level={2} style={styles.emptyTitle}>
              {emptyTitle}
            </HeadingText>
            <Text style={styles.emptyMessage}>{emptyMessage}</Text>
            {!debouncedSearch && status !== 'archived' ? (
              <PrimaryButton
                label={t('customers.list.create')}
                onPress={() => router.push('/customers/new')}
              />
            ) : null}
          </View>
        }
        ListFooterComponent={
          query.isFetchingNextPage ? (
            <View style={styles.loadingMore}>
              <ActivityIndicator color={colors.primary} />
              <Text style={styles.loadingMoreText}>{t('customers.list.loadingMore')}</Text>
            </View>
          ) : null
        }
        onEndReached={() => void loadMore()}
        onEndReachedThreshold={0.4}
        renderItem={({ item }) => (
          <CustomerRow
            customer={item}
            onPress={() => router.push(`/customers/${item.customer_code}`)}
          />
        )}
      />
    </SafeAreaView>
  );
}

function CustomerRow({ customer, onPress }: { customer: Customer; onPress: () => void }) {
  const { t } = useTranslation();
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.customerCard}>
      <View style={styles.customerTopRow}>
        <Text style={styles.customerName}>{customer.name}</Text>
        {customer.archived ? (
          <Text style={styles.archivedBadge}>{t('customers.list.archivedBadge')}</Text>
        ) : null}
      </View>
      <Text style={styles.customerCode}>{customer.customer_code}</Text>
      {customer.phone ? <Text style={styles.customerContact}>{customer.phone}</Text> : null}
      {customer.email ? <Text style={styles.customerContact}>{customer.email}</Text> : null}
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
  loadingMoreText: { color: colors.textMuted },
  updating: { alignItems: 'center', flexDirection: 'row', gap: spacing.sm },
  customerCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.md,
    borderWidth: 1,
    gap: spacing.xs,
    padding: spacing.md,
  },
  customerTopRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'space-between',
  },
  customerName: { color: colors.text, flex: 1, fontSize: 18, fontWeight: '700' },
  customerCode: { color: colors.primary, fontSize: 13, fontWeight: '700' },
  customerContact: { color: colors.textMuted, fontSize: 14 },
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
