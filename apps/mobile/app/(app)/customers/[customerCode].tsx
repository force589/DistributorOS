import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { apiClient } from '@/api/client';
import { ConfirmationDialog } from '@/components/ConfirmationDialog';
import { FeedbackBanner } from '@/components/FeedbackBanner';
import { FullScreenState } from '@/components/FullScreenState';
import { PrimaryButton } from '@/components/PrimaryButton';
import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import { HeadingText } from '@/design-system';
import { getCustomerErrorTranslationKey } from '@/features/customers/errorMessages';
import { getLedgerErrorTranslationKey } from '@/features/ledger/errorMessages';
import { formatLedgerDate } from '@/features/ledger/formatting';
import { formatInr } from '@/features/products/formatting';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';
import { formatLocalizedDate } from '@/formatting/presentation';

export default function CustomerDetailsScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useLocalSearchParams<{ customerCode: string; notice?: string }>();
  const customerCode = Array.isArray(params.customerCode)
    ? params.customerCode[0]
    : params.customerCode;
  const notice = Array.isArray(params.notice) ? params.notice[0] : params.notice;
  const [confirmation, setConfirmation] = useState<'archive' | 'restore' | null>(null);
  const [feedback, setFeedback] = useState<string | null>(
    notice === 'created'
      ? t('customers.create.success')
      : notice === 'updated'
        ? t('customers.edit.success')
        : null,
  );
  const [error, setError] = useState<string | null>(null);
  const { pending, run } = useSingleFlightAction();

  const query = useQuery({
    queryKey: ['customer', customerCode],
    queryFn: ({ signal }) => apiClient.getCustomerByCode(customerCode, signal),
    enabled: Boolean(customerCode),
  });
  const summaryQuery = useQuery({
    queryKey: ['customer-financial-summary', query.data?.id],
    queryFn: ({ signal }) => {
      if (!query.data?.id) throw new Error('Customer must load before its summary.');
      return apiClient.getCustomerFinancialSummary(query.data.id, signal);
    },
    enabled: Boolean(query.data?.id),
  });

  if (query.isPending) {
    return (
      <FullScreenState
        loading
        message={t('customers.details.loadingMessage')}
        title={t('customers.details.loadingTitle')}
      />
    );
  }
  if (query.isError || !query.data) {
    return (
      <FullScreenState
        actionLabel={t('common.back')}
        message={t('customers.details.errorMessage')}
        onAction={() => router.replace('/customers')}
        title={t('customers.details.errorTitle')}
      />
    );
  }

  const customer = query.data;
  const changeState = async () => {
    if (!confirmation) return;
    await run(async () => {
      setError(null);
      setFeedback(null);
      try {
        const result =
          confirmation === 'archive'
            ? await apiClient.archiveCustomer(customer.id)
            : await apiClient.restoreCustomer(customer.id);
        queryClient.setQueryData(['customer', customerCode], result.customer);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['customers'] }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        setFeedback(
          t(
            confirmation === 'archive'
              ? 'customers.archive.success'
              : 'customers.restore.success',
          ),
        );
        setConfirmation(null);
      } catch (stateError) {
        setError(t(getCustomerErrorTranslationKey(stateError, 'state')));
        setConfirmation(null);
      }
    });
  };

  const details: [string, string | null][] = [
    [t('customers.fields.customerCode'), customer.customer_code],
    [
      t('customers.fields.status'),
      customer.archived ? t('customers.filters.archived') : t('customers.details.active'),
    ],
    [t('customers.fields.phone'), customer.phone],
    [t('customers.fields.email'), customer.email],
    [t('customers.fields.addressLine1'), customer.address_line_1],
    [t('customers.fields.addressLine2'), customer.address_line_2],
    [t('customers.fields.city'), customer.city],
    [t('customers.fields.state'), customer.state],
    [t('customers.fields.postalCode'), customer.postal_code],
    [t('customers.fields.notes'), customer.notes],
    [
      t('customers.fields.createdAt'),
      formatLocalizedDate(customer.created_at, i18n.language, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }),
    ],
    [
      t('customers.fields.updatedAt'),
      formatLocalizedDate(customer.updated_at, i18n.language, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }),
    ],
  ];

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        actionLabel={t('customers.details.edit')}
        backLabel={t('common.back')}
        onAction={() => router.push(`/customers/edit/${customer.customer_code}`)}
        onBack={() => router.dismissTo('/customers')}
        title={t('customers.details.title')}
      />
      <ScrollView contentContainerStyle={styles.content}>
        {feedback ? <FeedbackBanner message={feedback} tone="success" /> : null}
        {error ? <FeedbackBanner message={error} /> : null}
        <View style={styles.card}>
          <HeadingText level={2} style={styles.name}>
            {customer.name}
          </HeadingText>
          <View style={styles.details}>
            {details
              .filter(([, value]) => Boolean(value))
              .map(([label, value]) => (
                <DetailRow key={label} label={label} value={value ?? ''} />
              ))}
          </View>
          <PrimaryButton
            destructive={!customer.archived}
            label={
              customer.archived
                ? t('customers.restore.action')
                : t('customers.archive.action')
            }
            onPress={() => setConfirmation(customer.archived ? 'restore' : 'archive')}
          />
        </View>
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>{t('ledger.summary.title')}</Text>
          {summaryQuery.isPending ? (
            <View style={styles.summaryLoading}>
              <ActivityIndicator color={colors.primary} />
              <Text style={styles.summaryMuted}>{t('ledger.summary.loading')}</Text>
            </View>
          ) : null}
          {summaryQuery.isError ? (
            <>
              <FeedbackBanner message={t(getLedgerErrorTranslationKey(summaryQuery.error))} />
              <PrimaryButton
                label={t('common.retry')}
                onPress={() => void summaryQuery.refetch()}
              />
            </>
          ) : null}
          {summaryQuery.data ? (
            <View style={styles.summaryGrid}>
              <FinancialMetric
                label={t('ledger.summary.outstandingBalance')}
                value={formatInr(summaryQuery.data.outstanding_balance, i18n.language)}
              />
              <FinancialMetric
                label={t('ledger.summary.availableCredit')}
                value={formatInr(summaryQuery.data.available_credit, i18n.language)}
              />
              <FinancialMetric
                label={t('ledger.summary.totalSales')}
                value={formatInr(summaryQuery.data.total_sales, i18n.language)}
              />
              <FinancialMetric
                label={t('ledger.summary.totalPayments')}
                value={formatInr(summaryQuery.data.total_payments, i18n.language)}
              />
              <FinancialMetric
                label={t('ledger.summary.lastSaleDate')}
                value={
                  summaryQuery.data.last_sale_date
                    ? formatLedgerDate(summaryQuery.data.last_sale_date, i18n.language)
                    : t('ledger.summary.noSales')
                }
              />
              <FinancialMetric
                label={t('ledger.summary.lastPaymentDate')}
                value={
                  summaryQuery.data.last_payment_date
                    ? formatLedgerDate(summaryQuery.data.last_payment_date, i18n.language)
                    : t('ledger.summary.noPayments')
                }
              />
            </View>
          ) : null}
          <PrimaryButton
            label={t('ledger.summary.viewLedger')}
            onPress={() => router.push(`/customers/ledger/${customer.customer_code}`)}
          />
          <PrimaryButton
            label={t('payments.customerHistory.viewPayments')}
            onPress={() => router.push(`/customers/payments/${customer.customer_code}`)}
          />
          <PrimaryButton
            label={t('invoices.customerHistory.viewInvoices')}
            onPress={() => router.push(`/customers/invoices/${customer.customer_code}`)}
          />
        </View>
      </ScrollView>
      <ConfirmationDialog
        cancelLabel={t('common.cancel')}
        confirmLabel={
          confirmation === 'restore'
            ? t('customers.restore.confirm')
            : t('customers.archive.confirm')
        }
        loading={pending}
        loadingLabel={
          confirmation === 'restore'
            ? t('customers.restore.loading')
            : t('customers.archive.loading')
        }
        message={
          confirmation === 'restore'
            ? t('customers.restore.message')
            : t('customers.archive.message')
        }
        onCancel={() => setConfirmation(null)}
        onConfirm={() => void changeState()}
        title={
          confirmation === 'restore'
            ? t('customers.restore.title')
            : t('customers.archive.title')
        }
        visible={confirmation !== null}
      />
    </SafeAreaView>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text selectable style={styles.detailValue}>
        {value}
      </Text>
    </View>
  );
}

function FinancialMetric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.financialMetric}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text selectable style={styles.financialValue}>{value}</Text>
    </View>
  );
}

const styles = ThemedStyleSheet.create({
  safeArea: { backgroundColor: colors.background, flex: 1 },
  content: {
    alignSelf: 'center',
    gap: spacing.md,
    maxWidth: 720,
    padding: spacing.lg,
    width: '100%',
  },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.lg,
    borderWidth: 1,
    gap: spacing.lg,
    padding: spacing.lg,
  },
  name: { color: colors.text, fontSize: 26, fontWeight: '800' },
  sectionTitle: { color: colors.text, fontSize: 20, fontWeight: '800' },
  details: { gap: spacing.md },
  detailRow: { borderBottomColor: colors.border, borderBottomWidth: 1, gap: spacing.xs, paddingBottom: spacing.md },
  detailLabel: { color: colors.textMuted, fontSize: 13, fontWeight: '700' },
  detailValue: { color: colors.text, fontSize: 16, lineHeight: 23 },
  summaryLoading: { alignItems: 'center', flexDirection: 'row', gap: spacing.sm },
  summaryMuted: { color: colors.textMuted, fontSize: 14 },
  summaryGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  financialMetric: {
    backgroundColor: colors.background,
    borderRadius: radii.md,
    flex: 1,
    gap: spacing.xs,
    minWidth: 180,
    padding: spacing.md,
  },
  financialValue: { color: colors.text, fontSize: 18, fontWeight: '800' },
});
