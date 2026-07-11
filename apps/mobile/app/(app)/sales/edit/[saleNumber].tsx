import { ApiError, type SaleCreateRequest } from '@distributoros/api-client';
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
import { getSaleErrorTranslationKey } from '@/features/sales/errorMessages';
import { SaleForm } from '@/features/sales/SaleForm';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';
import { useDirtyFormGuard } from '@/navigation/UnsavedChangesContext';

export default function EditSaleScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useLocalSearchParams<{ saleNumber: string }>();
  const saleNumber = Array.isArray(params.saleNumber) ? params.saleNumber[0] : params.saleNumber;
  const { pending, run } = useSingleFlightAction();
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const leaveAfterSave = useDirtyFormGuard(dirty);
  const query = useQuery({
    queryKey: ['sale', saleNumber],
    queryFn: ({ signal }) => apiClient.getSaleByNumber(saleNumber, signal),
    enabled: Boolean(saleNumber),
  });

  if (query.isPending) {
    return (
      <FullScreenState
        loading
        message={t('sales.details.loadingMessage')}
        title={t('sales.details.loadingTitle')}
      />
    );
  }
  if (query.isError || !query.data) {
    return (
      <FullScreenState
        actionLabel={t('common.back')}
        message={t('sales.details.errorMessage')}
        onAction={() => router.replace('/sales')}
        title={t('sales.details.errorTitle')}
      />
    );
  }
  if (query.data.status !== 'DRAFT') {
    return (
      <FullScreenState
        actionLabel={t('common.back')}
        message={t('sales.errors.notEditable')}
        onAction={() => router.replace(`/sales/${saleNumber}`)}
        title={t('sales.edit.title')}
      />
    );
  }

  const update = async (sale: SaleCreateRequest) => {
    await run(async () => {
      setError(null);
      setFieldErrors({});
      try {
        const result = await apiClient.updateSale(query.data.id, {
          ...sale,
          expected_updated_at: query.data.updated_at,
        });
        queryClient.setQueryData(['sale', saleNumber], result.sale);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['sales'] }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        leaveAfterSave(() => router.replace({
            pathname: '/sales/[saleNumber]',
            params: { saleNumber, notice: 'updated' },
          }));
      } catch (updateError) {
        if (updateError instanceof ApiError) setFieldErrors(updateError.fieldErrors);
        setError(t(getSaleErrorTranslationKey(updateError, 'save')));
      }
    });
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo(`/sales/${saleNumber}`)}
        subtitle={t('sales.edit.subtitle')}
        title={t('sales.edit.title')}
      />
      {error ? (
        <View style={styles.feedback}>
          <FeedbackBanner message={error} />
        </View>
      ) : null}
      <SaleForm
        actionLabel={t('sales.edit.action')}
        initialSale={query.data}
        loading={pending}
        onDirtyChange={setDirty}
        loadingLabel={t('sales.edit.loading')}
        onFieldChange={() => {
          setError(null);
          setFieldErrors({});
        }}
        onSubmit={update}
        serverFieldErrors={fieldErrors}
      />
    </SafeAreaView>
  );
}

const styles = ThemedStyleSheet.create({
  safeArea: { backgroundColor: colors.background, flex: 1 },
  feedback: { paddingHorizontal: spacing.lg, paddingTop: spacing.md },
});
