import { ApiError, type CustomerCreateRequest } from '@distributoros/api-client';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { apiClient } from '@/api/client';
import { FeedbackBanner } from '@/components/FeedbackBanner';
import { FullScreenState } from '@/components/FullScreenState';
import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, spacing } from '@/design/tokens';
import { CustomerForm } from '@/features/customers/CustomerForm';
import { getCustomerErrorTranslationKey } from '@/features/customers/errorMessages';
import type { CustomerField } from '@/features/customers/validation';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';
import { useDirtyFormGuard } from '@/navigation/UnsavedChangesContext';

export default function EditCustomerScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useLocalSearchParams<{ customerCode: string }>();
  const customerCode = Array.isArray(params.customerCode)
    ? params.customerCode[0]
    : params.customerCode;
  const { pending, run } = useSingleFlightAction();
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<CustomerField, string>>>({});
  const [dirty, setDirty] = useState(false);
  const leaveAfterSave = useDirtyFormGuard(dirty);
  const query = useQuery({
    queryKey: ['customer', customerCode],
    queryFn: ({ signal }) => apiClient.getCustomerByCode(customerCode, signal),
    enabled: Boolean(customerCode),
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
  const save = async (changes: CustomerCreateRequest) => {
    await run(async () => {
      setError(null);
      setFieldErrors({});
      try {
        const result = await apiClient.updateCustomer(customer.id, changes);
        queryClient.setQueryData(['customer', customerCode], result.customer);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['customers'] }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        leaveAfterSave(() => router.replace({
            pathname: '/customers/[customerCode]',
            params: { customerCode: result.customer.customer_code, notice: 'updated' },
          }));
      } catch (saveError) {
        if (
          saveError instanceof ApiError &&
          saveError.code === 'CUSTOMER_NAME_ALREADY_EXISTS'
        ) {
          setFieldErrors({ name: t('customers.validation.duplicateName') });
        }
        setError(t(getCustomerErrorTranslationKey(saveError, 'save')));
      }
    });
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo(`/customers/${customer.customer_code}`)}
        subtitle={t('customers.edit.subtitle')}
        title={t('customers.edit.title')}
      />
      {error ? (
        <View style={styles.feedback}>
          <FeedbackBanner message={error} />
        </View>
      ) : null}
      <CustomerForm
        actionLabel={t('customers.edit.action')}
        initialCustomer={customer}
        loading={pending}
        onDirtyChange={setDirty}
        loadingLabel={t('customers.edit.loading')}
        onFieldChange={(field) => {
          setFieldErrors((current) => ({ ...current, [field]: undefined }));
          setError(null);
        }}
        onSubmit={save}
        serverFieldErrors={fieldErrors}
      />
    </SafeAreaView>
  );
}

const styles = ThemedStyleSheet.create({
  safeArea: { backgroundColor: colors.background, flex: 1 },
  feedback: { paddingHorizontal: spacing.lg, paddingTop: spacing.md },
});
