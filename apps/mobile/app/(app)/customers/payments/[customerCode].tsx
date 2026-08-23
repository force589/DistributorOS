import { keepPreviousData, useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo, useRef } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Text,
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
import { getPaymentErrorTranslationKey } from '@/features/payments/errorMessages';
import { formatInr, paymentRowKey } from '@/features/payments/formatting';
import { PaymentListRow } from '@/features/payments/PaymentListRow';

export default function CustomerPaymentHistoryScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const params = useLocalSearchParams<{ customerCode: string }>();
  const customerCode = Array.isArray(params.customerCode)
    ? params.customerCode[0]
    : params.customerCode;
  const loadingMore = useRef(false);
  const customerQuery = useQuery({
    queryKey: ['customer', customerCode],
    queryFn: ({ signal }) => apiClient.getCustomerByCode(customerCode, signal),
    enabled: Boolean(customerCode),
  });
  const customerId = customerQuery.data?.id;
  const balanceQuery = useQuery({
    queryKey: ['customer-balance', customerId],
    queryFn: ({ signal }) => {
      if (!customerId) throw new Error('Customer must load before its payment balance.');
      return apiClient.getCustomerBalance(customerId, signal);
    },
    enabled: Boolean(customerId),
  });
  const paymentsQuery = useInfiniteQuery({
    queryKey: ['customer-payments', customerId],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) => {
      if (!customerId) throw new Error('Customer must load before its payments.');
      return apiClient.listCustomerPayments(customerId, {
        limit: 25,
        cursor: pageParam,
        sort: 'newest',
      }, signal);
    },
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    placeholderData: keepPreviousData,
    enabled: Boolean(customerId),
  });
  const payments = useMemo(
    () => paymentsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [paymentsQuery.data],
  );
  const loadMore = async () => {
    if (!paymentsQuery.hasNextPage || loadingMore.current) return;
    loadingMore.current = true;
    try {
      await paymentsQuery.fetchNextPage();
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
  if (paymentsQuery.isPending) {
    return (
      <FullScreenState
        loading
        message={t('payments.customerHistory.loadingMessage')}
        title={t('payments.customerHistory.loadingTitle')}
      />
    );
  }
  if (paymentsQuery.isError && payments.length === 0) {
    return (
      <FullScreenState
        actionLabel={t('common.retry')}
        message={t(getPaymentErrorTranslationKey(paymentsQuery.error))}
        onAction={() => void paymentsQuery.refetch()}
        title={t('payments.customerHistory.errorTitle')}
      />
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo(`/customers/${customerCode}`)}
        subtitle={`${customerQuery.data.name} • ${t('payments.customerHistory.subtitle')}`}
        title={t('payments.customerHistory.title')}
      />
      <View style={styles.summary}>
        {balanceQuery.isPending ? (
          <View style={styles.summaryLoading}>
            <ActivityIndicator color={colors.primary} size="small" />
            <Text style={styles.muted}>{t('payments.customerHistory.loadingBalance')}</Text>
          </View>
        ) : null}
        {balanceQuery.isError ? (
          <FeedbackBanner message={t(getPaymentErrorTranslationKey(balanceQuery.error))} />
        ) : null}
        {balanceQuery.data ? (
          <View style={styles.summaryGrid}>
            <Metric
              label={t('ledger.summary.outstandingBalance')}
              value={formatInr(balanceQuery.data.outstanding_balance, i18n.language)}
            />
            <Metric
              label={t('ledger.summary.availableCredit')}
              value={formatInr(balanceQuery.data.available_credit, i18n.language)}
            />
            <Metric
              label={t('ledger.summary.totalPayments')}
              value={formatInr(balanceQuery.data.total_payments, i18n.language)}
            />
          </View>
        ) : null}
      </View>
      {paymentsQuery.isRefetchError ? (
        <View style={styles.inlineError}>
          <FeedbackBanner message={t(getPaymentErrorTranslationKey(paymentsQuery.error))} />
        </View>
      ) : null}
      {paymentsQuery.isFetching && !paymentsQuery.isFetchingNextPage ? (
        <View style={styles.updating}>
          <ActivityIndicator color={colors.primary} size="small" />
          <Text style={styles.muted}>{t('payments.customerHistory.updating')}</Text>
        </View>
      ) : null}
      <FlatList
        contentContainerStyle={payments.length ? styles.list : styles.emptyList}
        data={payments}
        keyExtractor={paymentRowKey}
        ListEmptyComponent={
          <View style={styles.empty}>
            <HeadingText level={2} style={styles.emptyTitle}>
              {t('payments.customerHistory.emptyTitle')}
            </HeadingText>
            <Text style={styles.emptyMessage}>{t('payments.customerHistory.emptyMessage')}</Text>
          </View>
        }
        ListFooterComponent={paymentsQuery.isFetchingNextPage ? (
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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text selectable style={styles.metricValue}>{value}</Text>
    </View>
  );
}

const styles = ThemedStyleSheet.create({
  safeArea: { backgroundColor: colors.background, flex: 1 },
  summary: {
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    gap: spacing.sm,
    padding: spacing.md,
  },
  summaryLoading: { alignItems: 'center', flexDirection: 'row', gap: spacing.sm },
  summaryGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  metric: {
    backgroundColor: colors.background,
    borderRadius: radii.md,
    flex: 1,
    gap: spacing.xs,
    minWidth: 160,
    padding: spacing.md,
  },
  metricLabel: { color: colors.textMuted, fontSize: 12, fontWeight: '700' },
  metricValue: { color: colors.text, fontSize: 17, fontWeight: '800' },
  muted: { color: colors.textMuted, fontSize: 13 },
  inlineError: { padding: spacing.md },
  updating: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
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
