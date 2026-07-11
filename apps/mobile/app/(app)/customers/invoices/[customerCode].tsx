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
import { colors, spacing } from '@/design/tokens';
import { getInvoiceErrorTranslationKey } from '@/features/invoices/errorMessages';
import { invoiceRowKey } from '@/features/invoices/formatting';
import { InvoiceListRow } from '@/features/invoices/InvoiceListRow';

export default function CustomerInvoiceHistoryScreen() {
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
  const invoicesQuery = useInfiniteQuery({
    queryKey: ['customer-invoices', customerId],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) => {
      if (!customerId) throw new Error('Customer must load before its invoices.');
      return apiClient.listCustomerInvoices(customerId, {
        limit: 25,
        cursor: pageParam,
        sort: 'newest',
      }, signal);
    },
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    placeholderData: keepPreviousData,
    enabled: Boolean(customerId),
  });
  const invoices = useMemo(
    () => invoicesQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [invoicesQuery.data],
  );
  const loadMore = async () => {
    if (!invoicesQuery.hasNextPage || loadingMore.current) return;
    loadingMore.current = true;
    try {
      await invoicesQuery.fetchNextPage();
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
  if (invoicesQuery.isPending) {
    return (
      <FullScreenState
        loading
        message={t('invoices.customerHistory.loadingMessage')}
        title={t('invoices.customerHistory.loadingTitle')}
      />
    );
  }
  if (invoicesQuery.isError && invoices.length === 0) {
    return (
      <FullScreenState
        actionLabel={t('common.retry')}
        message={t(getInvoiceErrorTranslationKey(invoicesQuery.error))}
        onAction={() => void invoicesQuery.refetch()}
        title={t('invoices.customerHistory.errorTitle')}
      />
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo(`/customers/${customerCode}`)}
        subtitle={`${customerQuery.data.name} · ${t('invoices.customerHistory.subtitle')}`}
        title={t('invoices.customerHistory.title')}
      />
      {invoicesQuery.isRefetchError ? (
        <View style={styles.inlineError}>
          <FeedbackBanner message={t(getInvoiceErrorTranslationKey(invoicesQuery.error))} />
        </View>
      ) : null}
      {invoicesQuery.isFetching && !invoicesQuery.isFetchingNextPage ? (
        <View style={styles.updating}>
          <ActivityIndicator color={colors.primary} size="small" />
          <Text style={styles.muted}>{t('invoices.customerHistory.updating')}</Text>
        </View>
      ) : null}
      <FlatList
        contentContainerStyle={invoices.length ? styles.list : styles.emptyList}
        data={invoices}
        keyExtractor={invoiceRowKey}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text accessibilityRole="header" style={styles.emptyTitle}>
              {t('invoices.customerHistory.emptyTitle')}
            </Text>
            <Text style={styles.emptyMessage}>{t('invoices.customerHistory.emptyMessage')}</Text>
          </View>
        }
        ListFooterComponent={invoicesQuery.isFetchingNextPage ? (
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

const styles = ThemedStyleSheet.create({
  safeArea: { backgroundColor: colors.background, flex: 1 },
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
