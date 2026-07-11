import { ApiError, createIdempotencyKey, type PaymentCreateRequest } from '@distributoros/api-client';
import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { apiClient } from '@/api/client';
import { FeedbackBanner } from '@/components/FeedbackBanner';
import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, spacing } from '@/design/tokens';
import { getPaymentErrorTranslationKey } from '@/features/payments/errorMessages';
import { PaymentForm } from '@/features/payments/PaymentForm';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';
import { useDirtyFormGuard } from '@/navigation/UnsavedChangesContext';

export default function CreatePaymentScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { pending, run } = useSingleFlightAction();
  const idempotencyKey = useRef(createIdempotencyKey());
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const leaveAfterSave = useDirtyFormGuard(dirty);

  const create = async (payment: PaymentCreateRequest) => {
    await run(async () => {
      setError(null);
      setFieldErrors({});
      try {
        const result = await apiClient.createPayment(payment, idempotencyKey.current);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['payments'] }),
          queryClient.invalidateQueries({
            queryKey: ['customer-financial-summary', result.payment.customer_id],
          }),
          queryClient.invalidateQueries({ queryKey: ['customer-balance', result.payment.customer_id] }),
          queryClient.invalidateQueries({ queryKey: ['customer-credit', result.payment.customer_id] }),
          queryClient.invalidateQueries({ queryKey: ['customer-payments', result.payment.customer_id] }),
          queryClient.invalidateQueries({ queryKey: ['ledger', result.payment.customer_id] }),
          queryClient.invalidateQueries({ queryKey: ['invoices'] }),
          queryClient.invalidateQueries({ queryKey: ['invoice'] }),
          queryClient.invalidateQueries({
            queryKey: ['customer-invoices', result.payment.customer_id],
          }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        leaveAfterSave(() => router.replace({
            pathname: '/payments/[paymentNumber]',
            params: { paymentNumber: result.payment.payment_number, notice: 'created' },
          }));
      } catch (createError) {
        if (createError instanceof ApiError) setFieldErrors(createError.fieldErrors);
        setError(t(getPaymentErrorTranslationKey(createError, 'save')));
      }
    });
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo('/payments')}
        subtitle={t('payments.create.subtitle')}
        title={t('payments.create.title')}
      />
      {error ? (
        <View style={styles.feedback}>
          <FeedbackBanner message={error} />
        </View>
      ) : null}
      <PaymentForm
        actionLabel={t('payments.create.action')}
        loading={pending}
        onDirtyChange={setDirty}
        loadingLabel={t('payments.create.loading')}
        onFieldChange={() => {
          setError(null);
          setFieldErrors({});
        }}
        onSubmit={create}
        serverFieldErrors={fieldErrors}
      />
    </SafeAreaView>
  );
}

const styles = ThemedStyleSheet.create({
  safeArea: { backgroundColor: colors.background, flex: 1 },
  feedback: { paddingHorizontal: spacing.lg, paddingTop: spacing.md },
});
