import type {
  DatedReportOptions,
  InventoryReport,
  InventoryReportRow,
  LowStockReport,
  LowStockReportSort,
  OutstandingReport,
  OutstandingReportRow,
  OutstandingReportSort,
  PaymentReport,
  PaymentReportRow,
  ReportPeriod,
  ReportStatus,
  SalesReport,
  SalesReportRow,
  SalesReportSort,
  InventoryReportSort,
} from '@distributoros/api-client';
import { keepPreviousData, useInfiniteQuery } from '@tanstack/react-query';
import { type Href, useLocalSearchParams, useRouter } from 'expo-router';
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
import { PrimaryButton } from '@/components/PrimaryButton';
import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import { csvFilename, saveCsvFile } from '@/features/insights/csvExport';
import { getInsightsErrorTranslationKey } from '@/features/insights/errorMessages';
import {
  formatDate,
  formatDateTime,
  formatMoney,
  formatQuantity,
} from '@/features/insights/formatting';
import {
  datedReportSorts,
  inventoryReportSorts,
  isReportKind,
  lowStockReportSorts,
  outstandingReportSorts,
  paymentStatuses,
  reportPeriods,
  reportSubtitleKey,
  reportTitleKey,
  salesStatuses,
  type ReportKind,
} from '@/features/insights/reportDefinitions';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';

type ReportResponse =
  | SalesReport
  | PaymentReport
  | OutstandingReport
  | InventoryReport
  | LowStockReport;

type ReportRow =
  | SalesReportRow
  | PaymentReportRow
  | OutstandingReportRow
  | InventoryReportRow;

function validIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value);
}

function customDateErrorKey(
  period: string,
  dateFrom: string,
  dateTo: string,
): string | null {
  if (period !== 'custom') return null;
  if (!dateFrom || !dateTo) return 'insights.reports.validation.customDatesRequired';
  if (!validIsoDate(dateFrom) || !validIsoDate(dateTo)) {
    return 'insights.reports.validation.dateInvalid';
  }
  if (dateFrom > dateTo) return 'insights.reports.validation.dateOrder';
  return null;
}

export default function ReportDetailScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const params = useLocalSearchParams<{ report?: string }>();
  const rawReport = Array.isArray(params.report) ? params.report[0] : params.report;
  const reportKind: ReportKind = isReportKind(rawReport) ? rawReport : 'sales';
  const invalidReport = !isReportKind(rawReport);
  const [search, setSearch] = useState('');
  const [period, setPeriod] = useState<ReportPeriod>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [status, setStatus] = useState<ReportStatus>('all');
  const [datedSort, setDatedSort] = useState<SalesReportSort>('newest');
  const [outstandingSort, setOutstandingSort] =
    useState<OutstandingReportSort>('highest_outstanding');
  const [inventorySort, setInventorySort] = useState<InventoryReportSort>('name_asc');
  const [lowStockSort, setLowStockSort] = useState<LowStockReportSort>('lowest_stock');
  const [feedback, setFeedback] = useState<{
    message: string;
    tone: 'error' | 'success';
  } | null>(null);
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const loadingMore = useRef(false);
  const { pending: exporting, run: runExport } = useSingleFlightAction();
  const dateErrorKey = customDateErrorKey(period ?? 'all', dateFrom.trim(), dateTo.trim());
  const effectiveStatus = reportKind === 'payments' && status === 'draft' ? 'all' : status;
  const activeSort =
    reportKind === 'outstanding'
      ? outstandingSort
      : reportKind === 'inventory'
        ? inventorySort
        : reportKind === 'low-stock'
          ? lowStockSort
          : datedSort;

  const query = useInfiniteQuery<ReportResponse>({
    enabled: !invalidReport && !dateErrorKey,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    initialPageParam: undefined as string | undefined,
    placeholderData: keepPreviousData,
    queryFn: ({ pageParam, signal }) =>
      fetchReport(reportKind, {
        cursor: pageParam as string | undefined,
        dateFrom: dateFrom.trim(),
        dateTo: dateTo.trim(),
        period: period ?? 'all',
        search: debouncedSearch,
        sort: activeSort,
        status: effectiveStatus,
      }, signal),
    queryKey: [
      'reports',
      reportKind,
      period,
      dateFrom.trim(),
      dateTo.trim(),
      effectiveStatus,
      activeSort,
      debouncedSearch,
    ],
  });

  const rows = useMemo<ReportRow[]>(
    () => query.data?.pages.flatMap((page) => [...page.items] as ReportRow[]) ?? [],
    [query.data],
  );
  const visibleRows = dateErrorKey ? [] : rows;

  const loadMore = async () => {
    if (!query.hasNextPage || loadingMore.current || dateErrorKey) return;
    loadingMore.current = true;
    try {
      await query.fetchNextPage();
    } finally {
      loadingMore.current = false;
    }
  };

  const exportCsv = async () => {
    await runExport(async () => {
      setFeedback(null);
      try {
        const csv = await fetchCsv(reportKind, {
          dateFrom: dateFrom.trim(),
          dateTo: dateTo.trim(),
          period: period ?? 'all',
          search: debouncedSearch,
          sort: activeSort,
          status: effectiveStatus,
        });
        const result = await saveCsvFile(csvFilename(reportKind), csv);
        setFeedback({
          message: result.mode === 'downloaded'
            ? t('insights.reports.csvDownloaded', { file: result.uri })
            : t('insights.reports.csvShared', { file: result.uri }),
          tone: 'success',
        });
      } catch (error) {
        setFeedback({
          message: t(getInsightsErrorTranslationKey(error, 'csv')),
          tone: 'error',
        });
      }
    });
  };

  if (invalidReport) {
    return (
      <FullScreenState
        actionLabel={t('common.back')}
        message={t('insights.reports.invalidMessage')}
        onAction={() => router.push('/reports' as Href)}
        title={t('insights.reports.invalidTitle')}
      />
    );
  }

  if (query.isPending && !dateErrorKey) {
    return (
      <FullScreenState
        loading
        message={t('insights.reports.loadingMessage')}
        title={t('insights.reports.loadingTitle')}
      />
    );
  }

  if (query.isError && rows.length === 0) {
    return (
      <FullScreenState
        actionLabel={t('common.retry')}
        message={t(getInsightsErrorTranslationKey(query.error, 'report'))}
        onAction={() => void query.refetch()}
        title={t('insights.reports.errorTitle')}
      />
    );
  }

  const filtered = Boolean(
    debouncedSearch ||
      (isDatedReport(reportKind) && (period !== 'all' || effectiveStatus !== 'all')),
  );

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        actionLabel={t('insights.reports.exportCsv')}
        backLabel={t('common.back')}
        onAction={() => void exportCsv()}
        onBack={() => router.dismissTo('/reports' as Href)}
        subtitle={t(reportSubtitleKey(reportKind))}
        title={t(reportTitleKey(reportKind))}
      />
      <View style={styles.controls}>
        <TextInput
          accessibilityLabel={t('insights.reports.searchLabel')}
          autoCapitalize="none"
          onChangeText={setSearch}
          placeholder={t('insights.reports.searchPlaceholder')}
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={search}
        />
        {isDatedReport(reportKind) ? (
          <>
            <FilterRow
              label={t('insights.reports.periodLabel')}
              options={reportPeriods.map((value) => ({
                label: t(`insights.reports.periods.${periodKey(value)}`),
                value,
              }))}
              selected={period ?? 'all'}
              onSelect={(value) => setPeriod(value as ReportPeriod)}
            />
            {period === 'custom' ? (
              <View style={styles.dateRow}>
                <TextInput
                  accessibilityLabel={t('insights.reports.dateFromLabel')}
                  autoCapitalize="none"
                  keyboardType="numbers-and-punctuation"
                  maxLength={10}
                  onChangeText={setDateFrom}
                  placeholder={t('insights.reports.datePlaceholder')}
                  placeholderTextColor={colors.textMuted}
                  style={[styles.input, styles.dateInput]}
                  value={dateFrom}
                />
                <TextInput
                  accessibilityLabel={t('insights.reports.dateToLabel')}
                  autoCapitalize="none"
                  keyboardType="numbers-and-punctuation"
                  maxLength={10}
                  onChangeText={setDateTo}
                  placeholder={t('insights.reports.datePlaceholder')}
                  placeholderTextColor={colors.textMuted}
                  style={[styles.input, styles.dateInput]}
                  value={dateTo}
                />
              </View>
            ) : null}
            <FilterRow
              label={t('insights.reports.statusLabel')}
              options={(reportKind === 'payments' ? paymentStatuses : salesStatuses).map(
                (value) => ({
                  label: t(`insights.reports.status.${statusKey(value)}`),
                  value,
                }),
              )}
              selected={effectiveStatus}
              onSelect={(value) => setStatus(value as ReportStatus)}
            />
            <FilterRow
              label={t('insights.reports.sortLabel')}
              options={datedReportSorts.map((value) => ({
                label: t(`insights.reports.sorts.${sortKey(value)}`),
                value,
              }))}
              selected={datedSort ?? 'newest'}
              onSelect={(value) => setDatedSort(value as SalesReportSort)}
            />
          </>
        ) : reportKind === 'outstanding' ? (
          <FilterRow
            label={t('insights.reports.sortLabel')}
            options={outstandingReportSorts.map((value) => ({
              label: t(`insights.reports.sorts.${sortKey(value)}`),
              value,
            }))}
            selected={outstandingSort}
            onSelect={(value) => setOutstandingSort(value as OutstandingReportSort)}
          />
        ) : reportKind === 'inventory' ? (
          <FilterRow
            label={t('insights.reports.sortLabel')}
            options={inventoryReportSorts.map((value) => ({
              label: t(`insights.reports.sorts.${sortKey(value)}`),
              value,
            }))}
            selected={inventorySort}
            onSelect={(value) => setInventorySort(value as InventoryReportSort)}
          />
        ) : (
          <FilterRow
            label={t('insights.reports.sortLabel')}
            options={lowStockReportSorts.map((value) => ({
              label: t(`insights.reports.sorts.${sortKey(value)}`),
              value,
            }))}
            selected={lowStockSort}
            onSelect={(value) => setLowStockSort(value as LowStockReportSort)}
          />
        )}
        {dateErrorKey ? <FeedbackBanner message={t(dateErrorKey)} /> : null}
        {feedback ? <FeedbackBanner message={feedback.message} tone={feedback.tone} /> : null}
        {query.isFetching && !query.isFetchingNextPage ? (
          <View style={styles.updating}>
            <ActivityIndicator color={colors.primary} size="small" />
            <Text style={styles.muted}>{t('insights.reports.updating')}</Text>
          </View>
        ) : null}
        <PrimaryButton
          disabled={Boolean(dateErrorKey)}
          label={t('insights.reports.exportCsv')}
          loading={exporting}
          loadingLabel={t('insights.reports.exportingCsv')}
          onPress={() => void exportCsv()}
        />
      </View>
      {query.isRefetchError ? (
        <View style={styles.inlineError}>
          <FeedbackBanner message={t(getInsightsErrorTranslationKey(query.error, 'report'))} />
          <PrimaryButton label={t('common.retry')} onPress={() => void query.refetch()} />
        </View>
      ) : null}
      <FlatList
        contentContainerStyle={visibleRows.length ? styles.list : styles.emptyList}
        data={visibleRows}
        keyExtractor={(row) => reportRowKey(reportKind, row)}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text accessibilityRole="header" style={styles.emptyTitle}>
              {t(filtered ? 'insights.reports.noResultsTitle' : 'insights.reports.emptyTitle')}
            </Text>
            <Text style={styles.emptyMessage}>
              {t(filtered ? 'insights.reports.noResultsMessage' : 'insights.reports.emptyMessage')}
            </Text>
          </View>
        }
        ListFooterComponent={query.isFetchingNextPage ? (
          <View style={styles.loadingMore}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.muted}>{t('insights.reports.loadingMore')}</Text>
          </View>
        ) : null}
        onEndReached={() => void loadMore()}
        onEndReachedThreshold={0.4}
        renderItem={({ item }) => (
          <ReportRowCard
            kind={reportKind}
            row={item}
            onPress={() => openReportRow(reportKind, item, router.push)}
          />
        )}
      />
    </SafeAreaView>
  );
}

interface FetchOptions {
  cursor?: string;
  dateFrom: string;
  dateTo: string;
  period: ReportPeriod;
  search: string;
  sort: string;
  status: ReportStatus;
}

function datedOptions(options: FetchOptions): DatedReportOptions {
  return {
    cursor: options.cursor,
    dateFrom: options.period === 'custom' ? options.dateFrom : undefined,
    dateTo: options.period === 'custom' ? options.dateTo : undefined,
    limit: options.cursor ? 25 : 25,
    period: options.period,
    search: options.search || undefined,
    sort: options.sort as DatedReportOptions['sort'],
    status: options.status,
  };
}

function fetchReport(
  kind: ReportKind,
  options: FetchOptions,
  signal?: AbortSignal,
): Promise<ReportResponse> {
  if (kind === 'sales') return apiClient.salesReport(datedOptions(options), signal);
  if (kind === 'payments') return apiClient.paymentsReport(datedOptions(options), signal);
  if (kind === 'outstanding') {
    return apiClient.outstandingReport({
      cursor: options.cursor,
      limit: 25,
      search: options.search || undefined,
      sort: options.sort as OutstandingReportSort,
    }, signal);
  }
  if (kind === 'inventory') {
    return apiClient.inventoryReport({
      cursor: options.cursor,
      limit: 25,
      search: options.search || undefined,
      sort: options.sort as InventoryReportSort,
    }, signal);
  }
  return apiClient.lowStockReport({
    cursor: options.cursor,
    limit: 25,
    search: options.search || undefined,
    sort: options.sort as LowStockReportSort,
  }, signal);
}

function fetchCsv(kind: ReportKind, options: FetchOptions): Promise<string> {
  if (kind === 'sales') return apiClient.exportSalesCsv(datedOptions(options));
  if (kind === 'payments') return apiClient.exportPaymentsCsv(datedOptions(options));
  if (kind === 'outstanding') {
    return apiClient.exportOutstandingCsv({
      search: options.search || undefined,
      sort: options.sort as OutstandingReportSort,
    });
  }
  if (kind === 'inventory') {
    return apiClient.exportInventoryCsv({
      search: options.search || undefined,
      sort: options.sort as InventoryReportSort,
    });
  }
  return apiClient.exportLowStockCsv({
    search: options.search || undefined,
    sort: options.sort as LowStockReportSort,
  });
}

function isDatedReport(kind: ReportKind): boolean {
  return kind === 'sales' || kind === 'payments';
}

function periodKey(value: string): string {
  if (value === 'this_week') return 'thisWeek';
  if (value === 'this_month') return 'thisMonth';
  return value;
}

function statusKey(value: string): string {
  return sortKey(value.toLowerCase());
}

function sortKey(value: string): string {
  return value.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
}

function reportRowKey(kind: ReportKind, row: ReportRow): string {
  if (kind === 'sales') return (row as SalesReportRow).sale_number;
  if (kind === 'payments') return (row as PaymentReportRow).payment_number;
  if (kind === 'outstanding') return (row as OutstandingReportRow).customer_code;
  return (row as InventoryReportRow).product_code;
}

function openReportRow(
  kind: ReportKind,
  row: ReportRow,
  navigate: (href: Href) => void,
): void {
  if (kind === 'sales') {
    navigate(`/sales/${(row as SalesReportRow).sale_number}` as Href);
  } else if (kind === 'payments') {
    navigate(`/payments/${(row as PaymentReportRow).payment_number}` as Href);
  } else if (kind === 'outstanding') {
    navigate(`/customers/${(row as OutstandingReportRow).customer_code}` as Href);
  } else {
    navigate(`/inventory/${(row as InventoryReportRow).product_code}` as Href);
  }
}

function FilterRow({
  label,
  onSelect,
  options,
  selected,
}: {
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
            accessibilityRole="button"
            accessibilityState={{ selected: selected === option.value }}
            key={option.value}
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

function ReportRowCard({
  kind,
  onPress,
  row,
}: {
  kind: ReportKind;
  onPress: () => void;
  row: ReportRow;
}) {
  const { t } = useTranslation();
  if (kind === 'sales') {
    const sale = row as SalesReportRow;
    return (
      <Pressable accessibilityRole="button" onPress={onPress} style={styles.card}>
        <View style={styles.topRow}>
          <View style={styles.identity}>
            <Text style={styles.primary}>{sale.sale_number}</Text>
            <Text style={styles.secondary}>{sale.customer}</Text>
          </View>
          <Text style={styles.amount}>{formatMoney(sale.total)}</Text>
        </View>
        <Text style={styles.secondary}>{formatDate(sale.sale_date)}</Text>
        <Text style={styles.secondary}>
          {t('insights.reports.fields.items')}: {formatQuantity(sale.items)} ·{' '}
          {t(`insights.reports.status.${statusKey(sale.status)}`)}
        </Text>
      </Pressable>
    );
  }
  if (kind === 'payments') {
    const payment = row as PaymentReportRow;
    return (
      <Pressable accessibilityRole="button" onPress={onPress} style={styles.card}>
        <View style={styles.topRow}>
          <View style={styles.identity}>
            <Text style={styles.primary}>{payment.payment_number}</Text>
            <Text style={styles.secondary}>{payment.customer}</Text>
          </View>
          <Text style={styles.amount}>{formatMoney(payment.amount)}</Text>
        </View>
        <Text style={styles.secondary}>{formatDate(payment.payment_date)}</Text>
        <Text style={styles.secondary}>
          {t('insights.reports.fields.allocated')}: {formatMoney(payment.allocated)} ·{' '}
          {t('insights.reports.fields.unallocated')}: {formatMoney(payment.unallocated)}
        </Text>
      </Pressable>
    );
  }
  if (kind === 'outstanding') {
    const customer = row as OutstandingReportRow;
    return (
      <Pressable accessibilityRole="button" onPress={onPress} style={styles.card}>
        <View style={styles.topRow}>
          <View style={styles.identity}>
            <Text style={styles.primary}>{customer.customer}</Text>
            <Text style={styles.secondary}>{customer.customer_code}</Text>
          </View>
          <Text style={styles.amount}>{formatMoney(customer.outstanding_balance)}</Text>
        </View>
        <Text style={styles.secondary}>
          {t('insights.reports.fields.credit')}: {formatMoney(customer.available_credit)}
        </Text>
        <Text style={styles.secondary}>
          {t('insights.reports.fields.lastSale')}: {formatDateTime(customer.last_sale_at)} ·{' '}
          {t('insights.reports.fields.lastPayment')}: {formatDateTime(customer.last_payment_at)}
        </Text>
      </Pressable>
    );
  }
  const stock = row as InventoryReportRow;
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.card}>
      <View style={styles.topRow}>
        <View style={styles.identity}>
          <Text style={styles.primary}>{stock.product}</Text>
          <Text style={styles.secondary}>{stock.product_code}</Text>
        </View>
        <Text style={styles.amount}>{formatMoney(stock.inventory_value)}</Text>
      </View>
      <Text style={styles.secondary}>
        {formatQuantity(stock.current_stock, stock.unit)} ·{' '}
        {t(`insights.reports.stockStatus.${statusKey(stock.low_stock_status)}`)}
      </Text>
      <Text style={styles.secondary}>
        {t('insights.reports.fields.price')}: {formatMoney(stock.selling_price)}
      </Text>
    </Pressable>
  );
}

const styles = ThemedStyleSheet.create({
  safeArea: {
    backgroundColor: colors.background,
    flex: 1,
  },
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
  dateRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  dateInput: {
    flex: 1,
  },
  filterGroup: {
    gap: spacing.xs,
  },
  filterLabel: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: '700',
  },
  chips: {
    gap: spacing.sm,
  },
  chip: {
    borderColor: colors.border,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    justifyContent: 'center',
    minHeight: 44,
    paddingVertical: spacing.sm,
  },
  selectedChip: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '700',
  },
  selectedChipText: {
    color: colors.surface,
  },
  updating: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: spacing.sm,
  },
  inlineError: {
    gap: spacing.sm,
    padding: spacing.md,
  },
  list: {
    gap: spacing.md,
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  emptyList: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: spacing.xl,
  },
  empty: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.lg,
    borderWidth: 1,
    gap: spacing.sm,
    padding: spacing.xl,
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 20,
    fontWeight: '800',
    textAlign: 'center',
  },
  emptyMessage: {
    color: colors.textMuted,
    fontSize: 15,
    lineHeight: 22,
    textAlign: 'center',
  },
  loadingMore: {
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.lg,
  },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.lg,
    borderWidth: 1,
    gap: spacing.sm,
    padding: spacing.md,
  },
  topRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: spacing.md,
    justifyContent: 'space-between',
  },
  identity: {
    flex: 1,
    gap: spacing.xs,
  },
  primary: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '800',
  },
  secondary: {
    color: colors.textMuted,
    fontSize: 13,
    lineHeight: 19,
  },
  amount: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '800',
  },
  muted: {
    color: colors.textMuted,
    fontSize: 14,
  },
});
