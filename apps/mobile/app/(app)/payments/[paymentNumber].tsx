import { createIdempotencyKey } from '@distributoros/api-client';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
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
import { getPaymentErrorTranslationKey } from '@/features/payments/errorMessages';
import {
  formatInr,
  formatPaymentDate,
  formatPaymentDateTime,
  paymentMethodKeys,
  paymentStatusKeys,
} from '@/features/payments/formatting';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';

export default function PaymentDetailsScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useLocalSearchParams<{ paymentNumber: string; notice?: string }>();
  const paymentNumber = Array.isArray(params.paymentNumber)
    ? params.paymentNumber[0]
    : params.paymentNumber;
  const notice = Array.isArray(params.notice) ? params.notice[0] : params.notice;
  const [confirmingVoid, setConfirmingVoid] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(
    notice === 'created' ? t('payments.create.success') : null,
  );
  const [error, setError] = useState<string | null>(null);
  const voidKey = useRef(createIdempotencyKey());
  const { pending, run } = useSingleFlightAction();
  const query = useQuery({
    queryKey: ['payment', paymentNumber],
    queryFn: ({ signal }) => apiClient.getPaymentByNumber(paymentNumber, signal),
    enabled: Boolean(paymentNumber),
  });

  if (query.isPending) {
    return (
      <FullScreenState
        loading
        message={t('payments.details.loadingMessage')}
        title={t('payments.details.loadingTitle')}
      />
    );
  }
  if (query.isError || !query.data) {
    return (
      <FullScreenState
        actionLabel={t('common.back')}
        message={t('payments.details.errorMessage')}
        onAction={() => router.replace('/payments')}
        title={t('payments.details.errorTitle')}
      />
    );
  }

  const payment = query.data;
  const voidPayment = async () => {
    await run(async () => {
      setError(null);
      setFeedback(null);
      try {
        const result = await apiClient.voidPayment(payment.id, voidKey.current);
        queryClient.setQueryData(['payment', paymentNumber], result.payment);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['payments'] }),
          queryClient.invalidateQueries({
            queryKey: ['customer-financial-summary', payment.customer_id],
          }),
          queryClient.invalidateQueries({ queryKey: ['customer-balance', payment.customer_id] }),
          queryClient.invalidateQueries({ queryKey: ['customer-credit', payment.customer_id] }),
          queryClient.invalidateQueries({ queryKey: ['customer-payments', payment.customer_id] }),
          queryClient.invalidateQueries({ queryKey: ['ledger', payment.customer_id] }),
          queryClient.invalidateQueries({ queryKey: ['invoices'] }),
          queryClient.invalidateQueries({ queryKey: ['invoice'] }),
          queryClient.invalidateQueries({ queryKey: ['customer-invoices', payment.customer_id] }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        setFeedback(t('payments.void.success'));
        setConfirmingVoid(false);
      } catch (voidError) {
        setError(t(getPaymentErrorTranslationKey(voidError, 'lifecycle')));
        setConfirmingVoid(false);
      }
    });
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo('/payments')}
        title={t('payments.details.title')}
      />
      <ScrollView contentContainerStyle={styles.content}>
        {feedback ? <FeedbackBanner message={feedback} tone="success" /> : null}
        {error ? <FeedbackBanner message={error} /> : null}
        {payment.status === 'VOID' ? (
          <FeedbackBanner message={t('payments.details.voidNotice')} />
        ) : null}
        <View style={styles.card}>
          <Text accessibilityRole="header" style={styles.paymentNumber}>{payment.payment_number}</Text>
          <DetailRow label={t('payments.details.customer')} value={payment.customer_name} />
          <DetailRow label={t('payments.details.status')} value={t(paymentStatusKeys[payment.status])} />
          <DetailRow
            label={t('payments.details.paymentDate')}
            value={formatPaymentDate(payment.payment_date, i18n.language)}
          />
          <DetailRow
            label={t('payments.details.createdAt')}
            value={formatPaymentDateTime(payment.created_at, i18n.language)}
          />
          <DetailRow label={t('payments.details.amount')} value={formatInr(payment.amount, i18n.language)} />
          <DetailRow label={t('payments.details.method')} value={t(paymentMethodKeys[payment.payment_method])} />
          <DetailRow
            label={t('payments.details.referenceNumber')}
            value={payment.reference_number || t('payments.details.noReference')}
          />
          <DetailRow label={t('payments.details.notes')} value={payment.notes || t('payments.details.noNotes')} />
          <DetailRow
            label={t('payments.details.allocatedAmount')}
            value={formatInr(payment.allocated_amount, i18n.language)}
          />
          <DetailRow
            label={t('payments.details.unallocatedAmount')}
            value={formatInr(payment.unallocated_amount, i18n.language)}
          />
        </View>
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>{t('payments.details.allocations')}</Text>
          {payment.allocations.length === 0 ? (
            <Text style={styles.muted}>{t('payments.details.noAllocations')}</Text>
          ) : null}
          {payment.allocations.map((allocation) => (
            <View key={allocation.id} style={styles.allocation}>
              <Text style={styles.allocationReference}>{allocation.reference}</Text>
              <Text style={styles.muted}>
                {t(
                  allocation.reference_type === 'INVOICE'
                    ? 'payments.details.invoiceAllocation'
                    : allocation.reference_type === 'SALE'
                      ? 'ledger.entryTypes.sale'
                      : 'ledger.entryTypes.payment',
                )}
              </Text>
              <Text style={styles.allocationAmount}>
                {formatInr(allocation.allocated_amount, i18n.language)}
              </Text>
            </View>
          ))}
        </View>
        {payment.status === 'POSTED' ? (
          <PrimaryButton
            destructive
            label={t('payments.void.action')}
            onPress={() => setConfirmingVoid(true)}
          />
        ) : null}
      </ScrollView>
      <ConfirmationDialog
        cancelLabel={t('common.cancel')}
        confirmLabel={t('payments.void.confirm')}
        loading={pending}
        loadingLabel={t('payments.void.loading')}
        message={t('payments.void.message')}
        onCancel={() => setConfirmingVoid(false)}
        onConfirm={() => void voidPayment()}
        title={t('payments.void.title')}
        visible={confirmingVoid}
      />
    </SafeAreaView>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text selectable style={styles.detailValue}>{value}</Text>
    </View>
  );
}

const styles = ThemedStyleSheet.create({
  safeArea: { backgroundColor: colors.background, flex: 1 },
  content: {
    alignSelf: 'center',
    gap: spacing.md,
    maxWidth: 760,
    padding: spacing.lg,
    width: '100%',
  },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.lg,
    borderWidth: 1,
    gap: spacing.md,
    padding: spacing.lg,
  },
  paymentNumber: { color: colors.primary, fontSize: 26, fontWeight: '800' },
  sectionTitle: { color: colors.text, fontSize: 19, fontWeight: '800' },
  detailRow: {
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    gap: spacing.xs,
    paddingBottom: spacing.md,
  },
  detailLabel: { color: colors.textMuted, fontSize: 13, fontWeight: '700' },
  detailValue: { color: colors.text, fontSize: 16, lineHeight: 23 },
  allocation: {
    backgroundColor: colors.background,
    borderRadius: radii.md,
    gap: spacing.xs,
    padding: spacing.md,
  },
  allocationReference: { color: colors.text, fontSize: 16, fontWeight: '800' },
  allocationAmount: { color: colors.text, fontSize: 15, fontWeight: '800' },
  muted: { color: colors.textMuted, fontSize: 14 },
});
