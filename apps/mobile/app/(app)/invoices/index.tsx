import type { InvoiceSort, InvoiceStatus } from '@distributoros/api-client';
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
import { HeadingText } from '@/design-system';
import { getInvoiceErrorTranslationKey } from '@/features/invoices/errorMessages';
import { invoiceRowKey, invoiceStatusKeys } from '@/features/invoices/formatting';
import { InvoiceListRow } from '@/features/invoices/InvoiceListRow';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

const statuses: InvoiceStatus[] = ['all', 'draft', 'issued', 'void'];
const sorts: InvoiceSort[] = ['newest', 'oldest'];

function validIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value);
}

export default function InvoicesListScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [date, setDate] = useState('');
  const [status, setStatus] = useState<InvoiceStatus>('all');
  const [sort, setSort] = useState<InvoiceSort>('newest');
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const debouncedDate = useDebouncedValue(date.trim(), 300);
  const dateError = Boolean(debouncedDate) && !validIsoDate(debouncedDate);
  const loadingMore = useRef(false);
  const query = useInfiniteQuery({
    queryKey: ['invoices', 'list', status, sort, debouncedSearch, debouncedDate],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) => apiClient.listInvoices({
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
  const invoices = useMemo(
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
        message={t('invoices.list.loadingMessage')}
        title={t('invoices.list.loadingTitle')}
      />
    );
  }
  if (query.isError && invoices.length === 0) {
    return (
      <FullScreenState
        actionLabel={t('common.retry')}
        message={t(getInvoiceErrorTranslationKey(query.error))}
        onAction={() => void query.refetch()}
        title={t('invoices.list.errorTitle')}
      />
    );
  }
  const filtered = Boolean(debouncedSearch || debouncedDate || status !== 'all');

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        actionLabel={t('invoices.list.create')}
        level="primary"
        onAction={() => router.push('/invoices/new')}
        subtitle={t('invoices.list.subtitle')}
        title={t('invoices.list.title')}
      />
      <View style={styles.controls}>
        <TextInput
          accessibilityLabel={t('invoices.list.searchLabel')}
          autoCapitalize="characters"
          onChangeText={setSearch}
          placeholder={t('invoices.list.searchPlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={search}
        />
        <TextInput
          accessibilityLabel={t('invoices.list.dateLabel')}
          keyboardType="numbers-and-punctuation"
          maxLength={10}
          onChangeText={setDate}
          placeholder={t('invoices.list.datePlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={date}
        />
        {dateError ? <Text style={styles.error}>{t('invoices.validation.dateInvalid')}</Text> : null}
        <FilterRow
          label={t('invoices.list.filterLabel')}
          options={statuses.map((value) => ({
            value,
            label: value === 'all' ? t('invoices.filters.all') : t(invoiceStatusKeys[value]),
          }))}
          selected={status}
          onSelect={(value) => setStatus(value as InvoiceStatus)}
        />
        <FilterRow
          label={t('invoices.list.sortLabel')}
          options={sorts.map((value) => ({
            value,
            label: t(value === 'newest' ? 'invoices.sorts.newest' : 'invoices.sorts.oldest'),
          }))}
          selected={sort}
          onSelect={(value) => setSort(value as InvoiceSort)}
        />
        {query.isFetching && !query.isFetchingNextPage ? (
          <View style={styles.updating}>
            <ActivityIndicator color={colors.primary} size="small" />
            <Text style={styles.muted}>{t('invoices.list.updating')}</Text>
          </View>
        ) : null}
      </View>
      {query.isRefetchError ? (
        <View style={styles.inlineError}>
          <FeedbackBanner message={t(getInvoiceErrorTranslationKey(query.error))} />
        </View>
      ) : null}
      <FlatList
        contentContainerStyle={invoices.length ? styles.list : styles.emptyList}
        data={invoices}
        keyExtractor={invoiceRowKey}
        ListEmptyComponent={
          <View style={styles.empty}>
            <HeadingText level={2} style={styles.emptyTitle}>
              {t(filtered ? 'invoices.list.noResultsTitle' : 'invoices.list.emptyTitle')}
            </HeadingText>
            <Text style={styles.emptyMessage}>
              {t(filtered ? 'invoices.list.noResultsMessage' : 'invoices.list.emptyMessage')}
            </Text>
          </View>
        }
        ListFooterComponent={query.isFetchingNextPage ? (
          <View style={styles.loadingMore}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.muted}>{t('invoices.list.loadingMore')}</Text>
          </View>
        ) : null}
        onEndReached={() => void loadMore()}
        onEndReachedThreshold={0.4}
        renderItem={({ item }) => (
          <InvoiceListRow
            item={item}
            language={i18n.language}
            onPress={() => router.push(`/invoices/${item.invoice_number}`)}
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
