import { ApiError, type CustomerCreateRequest } from '@distributoros/api-client';
import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { apiClient } from '@/api/client';
import { FeedbackBanner } from '@/components/FeedbackBanner';
import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, spacing } from '@/design/tokens';
import { CustomerForm } from '@/features/customers/CustomerForm';
import { getCustomerErrorTranslationKey } from '@/features/customers/errorMessages';
import type { CustomerField } from '@/features/customers/validation';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';
import { useDirtyFormGuard } from '@/navigation/UnsavedChangesContext';

export default function CreateCustomerScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { pending, run } = useSingleFlightAction();
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<CustomerField, string>>>({});
  const [dirty, setDirty] = useState(false);
  const leaveAfterSave = useDirtyFormGuard(dirty);

  const create = async (customer: CustomerCreateRequest) => {
    await run(async () => {
      setError(null);
      setFieldErrors({});
      try {
        const result = await apiClient.createCustomer(customer);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['customers'] }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        leaveAfterSave(() => router.replace({
            pathname: '/customers/[customerCode]',
            params: { customerCode: result.customer.customer_code, notice: 'created' },
          }));
      } catch (createError) {
        if (
          createError instanceof ApiError &&
          createError.code === 'CUSTOMER_NAME_ALREADY_EXISTS'
        ) {
          setFieldErrors({ name: t('customers.validation.duplicateName') });
        }
        setError(t(getCustomerErrorTranslationKey(createError, 'save')));
      }
    });
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo('/customers')}
        subtitle={t('customers.create.subtitle')}
        title={t('customers.create.title')}
      />
      {error ? (
        <View style={styles.feedback}>
          <FeedbackBanner message={error} />
        </View>
      ) : null}
      <CustomerForm
        actionLabel={t('customers.create.action')}
        loading={pending}
        onDirtyChange={setDirty}
        loadingLabel={t('customers.create.loading')}
        onFieldChange={(field) => {
          setFieldErrors((current) => ({ ...current, [field]: undefined }));
          setError(null);
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
