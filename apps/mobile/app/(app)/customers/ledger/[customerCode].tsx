import type { LedgerEntry, LedgerEntryType } from '@distributoros/api-client';
import { keepPreviousData, useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
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
import { getLedgerErrorTranslationKey } from '@/features/ledger/errorMessages';
import {
  formatLedgerDate,
  isValidLedgerDate,
  ledgerEntryTypeKeys,
} from '@/features/ledger/formatting';
import { formatInr } from '@/features/products/formatting';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

const entryTypes: LedgerEntryType[] = ['all', 'sale', 'reversal', 'payment', 'payment_reversal'];

export default function CustomerLedgerScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const params = useLocalSearchParams<{ customerCode: string }>();
  const customerCode = Array.isArray(params.customerCode)
    ? params.customerCode[0]
    : params.customerCode;
  const [reference, setReference] = useState('');
  const [date, setDate] = useState('');
  const [entryType, setEntryType] = useState<LedgerEntryType>('all');
  const debouncedReference = useDebouncedValue(reference.trim(), 300);
  const debouncedDate = useDebouncedValue(date.trim(), 300);
  const dateError = Boolean(debouncedDate) && !isValidLedgerDate(debouncedDate);
  const loadingMore = useRef(false);
  const customerQuery = useQuery({
    queryKey: ['customer', customerCode],
    queryFn: ({ signal }) => apiClient.getCustomerByCode(customerCode, signal),
    enabled: Boolean(customerCode),
  });
  const customerId = customerQuery.data?.id;
  const ledgerQuery = useInfiniteQuery({
    queryKey: [
      'ledger',
      customerId,
      entryType,
      debouncedReference,
      debouncedDate,
    ],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) => {
      if (!customerId) throw new Error('Customer must load before its ledger.');
      return apiClient.listCustomerLedger(
        customerId,
        {
          entryType,
          reference: debouncedReference || undefined,
          date: !dateError && debouncedDate ? debouncedDate : undefined,
          limit: 25,
          cursor: pageParam,
        },
        signal,
      );
    },
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    placeholderData: keepPreviousData,
    enabled: Boolean(customerId) && !dateError,
  });
  const entries = useMemo(
    () => ledgerQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [ledgerQuery.data],
  );
  const loadMore = async () => {
    if (!ledgerQuery.hasNextPage || loadingMore.current) return;
    loadingMore.current = true;
    try {
      await ledgerQuery.fetchNextPage();
    } finally {
      loadingMore.current = false;
    }
  };

  if (customerQuery.isPending) {
    return (
      <FullScreenState
        loading
        message={t('customers.details.loadingMessage')}
        title={t('customers.details.loadingTitle')}
      />
    );
  }
  if (customerQuery.isError || !customerQuery.data) {
    return (
      <FullScreenState
        actionLabel={t('common.back')}
        message={t('customers.details.errorMessage')}
        onAction={() => router.replace('/customers')}
        title={t('customers.details.errorTitle')}
      />
    );
  }
  if (ledgerQuery.isPending) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <ScreenHeader
          backLabel={t('common.back')}
          onBack={() => router.dismissTo(`/customers/${customerCode}`)}
          subtitle={`${customerQuery.data.name} · ${t('ledger.list.subtitle')}`}
          title={t('ledger.list.title')}
        />
        <ListSkeleton
          accessibilityLabel={`${t('ledger.list.loadingTitle')}. ${t('ledger.list.loadingMessage')}`}
        />
      </SafeAreaView>
    );
  }
  if (ledgerQuery.isError && entries.length === 0) {
    return (
      <FullScreenState
        actionLabel={t('common.retry')}
        message={t(getLedgerErrorTranslationKey(ledgerQuery.error))}
        onAction={() => void ledgerQuery.refetch()}
        title={t('ledger.list.errorTitle')}
      />
    );
  }
  const filtered = Boolean(debouncedReference || debouncedDate || entryType !== 'all');

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo(`/customers/${customerCode}`)}
        subtitle={`${customerQuery.data.name} · ${t('ledger.list.subtitle')}`}
        title={t('ledger.list.title')}
      />
      <View style={styles.controls}>
        <TextInput
          accessibilityLabel={t('ledger.list.searchLabel')}
          autoCapitalize="characters"
          onChangeText={setReference}
          placeholder={t('ledger.list.searchPlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={reference}
        />
        <TextInput
          accessibilityLabel={t('ledger.list.dateLabel')}
          keyboardType="numbers-and-punctuation"
          maxLength={10}
          onChangeText={setDate}
          placeholder={t('ledger.list.datePlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={date}
        />
        {dateError ? <Text style={styles.error}>{t('ledger.validation.dateInvalid')}</Text> : null}
        <FilterChipGroup
          label={t('ledger.list.typeLabel')}
          onSelect={(value) => setEntryType(value as LedgerEntryType)}
          options={entryTypes.map((value) => ({
            label: t(value === 'all' ? 'ledger.filters.all' : ledgerEntryTypeKeys[value]),
            value,
          }))}
          selected={entryType}
          testIDPrefix="ledger-type"
        />
        {ledgerQuery.isFetching && !ledgerQuery.isFetchingNextPage ? (
          <View style={styles.updating}>
            <ActivityIndicator color={colors.primary} size="small" />
            <Text style={styles.muted}>{t('ledger.list.updating')}</Text>
          </View>
        ) : null}
      </View>
      {ledgerQuery.isRefetchError ? (
        <View style={styles.inlineError}>
          <FeedbackBanner message={t(getLedgerErrorTranslationKey(ledgerQuery.error))} />
        </View>
      ) : null}
      <FlatList
        contentContainerStyle={entries.length ? styles.list : styles.emptyList}
        data={entries}
        keyExtractor={(entry) => entry.id}
        ListEmptyComponent={
          <View style={styles.empty}>
            <HeadingText level={2} style={styles.emptyTitle}>
              {t(filtered ? 'ledger.list.noResultsTitle' : 'ledger.list.emptyTitle')}
            </HeadingText>
            <Text style={styles.emptyMessage}>
              {t(filtered ? 'ledger.list.noResultsMessage' : 'ledger.list.emptyMessage')}
            </Text>
          </View>
        }
        ListFooterComponent={ledgerQuery.isFetchingNextPage ? (
          <View style={styles.loadingMore}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.muted}>{t('ledger.list.loadingMore')}</Text>
          </View>
        ) : null}
        onEndReached={() => void loadMore()}
        onEndReachedThreshold={0.4}
        renderItem={({ item }) => (
          <LedgerRow
            entry={item}
            language={i18n.language}
            onReference={() => {
              if (item.reference_type === 'PAYMENT') {
                router.push(`/payments/${item.reference}`);
              } else {
                router.push(`/sales/${item.reference}`);
              }
            }}
          />
        )}
      />
    </SafeAreaView>
  );
}

function LedgerRow({
  entry,
  language,
  onReference,
}: {
  entry: LedgerEntry;
  language: string;
  onReference: () => void;
}) {
  const { t } = useTranslation();
  return (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <View style={styles.identity}>
          <Text style={styles.type}>{t(ledgerEntryTypeKeys[entry.entry_type])}</Text>
          <Text style={styles.muted}>{formatLedgerDate(entry.created_at, language)}</Text>
        </View>
        <Pressable accessibilityRole="button" onPress={onReference}>
          <Text style={styles.reference}>{entry.reference}</Text>
        </Pressable>
      </View>
      <View style={styles.amounts}>
        <Amount label={t('ledger.fields.debit')} value={formatInr(entry.debit, language)} />
        <Amount label={t('ledger.fields.credit')} value={formatInr(entry.credit, language)} />
        <Amount
          emphasized
          label={t('ledger.fields.runningBalance')}
          value={formatInr(entry.running_balance, language)}
        />
      </View>
      <Text style={styles.remarks}>
        {t('ledger.fields.remarks')}: {entry.remarks || t('ledger.fields.noRemarks')}
      </Text>
    </View>
  );
}

function Amount({
  emphasized = false,
  label,
  value,
}: {
  emphasized?: boolean;
  label: string;
  value: string;
}) {
  return (
    <View style={styles.amount}>
      <Text style={styles.amountLabel}>{label}</Text>
      <Text style={[styles.amountValue, emphasized && styles.emphasized]}>{value}</Text>
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
    gap: spacing.md,
    padding: spacing.md,
  },
  topRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'space-between',
  },
  identity: { flex: 1, gap: spacing.xs },
  type: { color: colors.text, fontSize: 17, fontWeight: '800' },
  reference: { color: colors.primary, fontSize: 14, fontWeight: '800' },
  amounts: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  amount: { flex: 1, gap: spacing.xs, minWidth: 120 },
  amountLabel: { color: colors.textMuted, fontSize: 12, fontWeight: '700' },
  amountValue: { color: colors.text, fontSize: 15, fontWeight: '700' },
  emphasized: { color: colors.primary, fontSize: 17 },
  remarks: { color: colors.textMuted, fontSize: 13 },
});
