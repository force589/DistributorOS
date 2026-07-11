import type { PaymentMethod, PaymentSort, PaymentStatus } from '@distributoros/api-client';
import { keepPreviousData, useInfiniteQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
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
import { FullScreenState } from '@/components/FullScreenState';
import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import { getPaymentErrorTranslationKey } from '@/features/payments/errorMessages';
import {
  paymentMethodKeys,
  paymentRowKey,
  paymentStatusKeys,
} from '@/features/payments/formatting';
import { PaymentListRow } from '@/features/payments/PaymentListRow';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

const statuses: PaymentStatus[] = ['all', 'posted', 'void'];
const methods: PaymentMethod[] = ['all', 'cash', 'upi', 'bank_transfer', 'cheque', 'other'];
const sorts: PaymentSort[] = ['newest', 'oldest'];

function validIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value);
}

export default function PaymentsListScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [date, setDate] = useState('');
  const [status, setStatus] = useState<PaymentStatus>('all');
  const [method, setMethod] = useState<PaymentMethod>('all');
  const [sort, setSort] = useState<PaymentSort>('newest');
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const debouncedDate = useDebouncedValue(date.trim(), 300);
  const dateError = Boolean(debouncedDate) && !validIsoDate(debouncedDate);
  const loadingMore = useRef(false);
  const query = useInfiniteQuery({
    queryKey: ['payments', 'list', status, method, sort, debouncedSearch, debouncedDate],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) => apiClient.listPayments({
      status,
      method,
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
  const payments = useMemo(
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
      <FullScreenState
        loading
        message={t('payments.list.loadingMessage')}
        title={t('payments.list.loadingTitle')}
      />
    );
  }
  if (query.isError && payments.length === 0) {
    return (
      <FullScreenState
        actionLabel={t('common.retry')}
        message={t('payments.list.errorMessage')}
        onAction={() => void query.refetch()}
        title={t('payments.list.errorTitle')}
      />
    );
  }
  const filtered = Boolean(debouncedSearch || debouncedDate || status !== 'all' || method !== 'all');

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        actionLabel={t('payments.list.create')}
        backLabel={t('common.back')}
        onAction={() => router.push('/payments/new')}
        onBack={() => router.dismissTo('/(app)')}
        subtitle={t('payments.list.subtitle')}
        title={t('payments.list.title')}
      />
      <View style={styles.controls}>
        <TextInput
          accessibilityLabel={t('payments.list.searchLabel')}
          autoCapitalize="none"
          onChangeText={setSearch}
          placeholder={t('payments.list.searchPlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={search}
        />
        <TextInput
          accessibilityLabel={t('payments.list.dateLabel')}
          autoCapitalize="none"
          keyboardType="numbers-and-punctuation"
          maxLength={10}
          onChangeText={setDate}
          placeholder={t('payments.list.datePlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={date}
        />
        {dateError ? <Text style={styles.error}>{t('payments.validation.dateInvalid')}</Text> : null}
        <FilterRow
          label={t('payments.list.filterLabel')}
          options={statuses.map((value) => ({
            value,
            label: value === 'all' ? t('payments.filters.all') : t(paymentStatusKeys[value]),
          }))}
          selected={status}
          onSelect={(value) => setStatus(value as PaymentStatus)}
        />
        <FilterRow
          label={t('payments.list.methodLabel')}
          options={methods.map((value) => ({
            value,
            label: value === 'all' ? t('payments.methods.all') : t(paymentMethodKeys[value]),
          }))}
          selected={method}
          onSelect={(value) => setMethod(value as PaymentMethod)}
        />
        <FilterRow
          label={t('payments.list.sortLabel')}
          options={sorts.map((value) => ({
            value,
            label: t(value === 'newest' ? 'payments.sorts.newest' : 'payments.sorts.oldest'),
          }))}
          selected={sort}
          onSelect={(value) => setSort(value as PaymentSort)}
        />
        {query.isFetching && !query.isFetchingNextPage ? (
          <View style={styles.updating}>
            <ActivityIndicator color={colors.primary} size="small" />
            <Text style={styles.muted}>{t('payments.list.updating')}</Text>
          </View>
        ) : null}
      </View>
      {query.isRefetchError ? (
        <View style={styles.inlineError}>
          <FeedbackBanner message={t(getPaymentErrorTranslationKey(query.error))} />
        </View>
      ) : null}
      <FlatList
        contentContainerStyle={payments.length ? styles.list : styles.emptyList}
        data={payments}
        keyExtractor={paymentRowKey}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text accessibilityRole="header" style={styles.emptyTitle}>
              {t(filtered ? 'payments.list.noResultsTitle' : 'payments.list.emptyTitle')}
            </Text>
            <Text style={styles.emptyMessage}>
              {t(filtered ? 'payments.list.noResultsMessage' : 'payments.list.emptyMessage')}
            </Text>
          </View>
        }
        ListFooterComponent={query.isFetchingNextPage ? (
          <View style={styles.loadingMore}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.muted}>{t('payments.list.loadingMore')}</Text>
          </View>
        ) : null}
        onEndReached={() => void loadMore()}
        onEndReachedThreshold={0.4}
        renderItem={({ item }) => (
          <PaymentListRow
            item={item}
            language={i18n.language}
            onPress={() => router.push(`/payments/${item.payment_number}`)}
          />
        )}
      />
    </SafeAreaView>
  );
}

function FilterRow({ label, onSelect, options, selected }: {
  label: string;
  onSelect: (value: string) => void;
  options: { value: string; label: string }[];
  selected: string;
}) {
  return (
    <View style={styles.filterGroup}>
      <Text style={styles.filterLabel}>{label}</Text>
      <ScrollView contentContainerStyle={styles.chips} horizontal showsHorizontalScrollIndicator={false}>
        {options.map((option) => (
          <Pressable
            key={option.value}
            accessibilityRole="button"
            accessibilityState={{ selected: selected === option.value }}
            onPress={() => onSelect(option.value)}
            style={[styles.chip, selected === option.value && styles.selectedChip]}
          >
            <Text style={[styles.chipText, selected === option.value && styles.selectedChipText]}>
              {option.label}
            </Text>
          </Pressable>
        ))}
      </ScrollView>
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
  filterGroup: { gap: spacing.xs },
  filterLabel: { color: colors.textMuted, fontSize: 12, fontWeight: '700' },
  chips: { gap: spacing.sm },
  chip: {
    borderColor: colors.border,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    justifyContent: 'center',
    minHeight: 44,
    paddingVertical: spacing.sm,
  },
  selectedChip: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.text, fontSize: 13, fontWeight: '700' },
  selectedChipText: { color: colors.surface },
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
});
