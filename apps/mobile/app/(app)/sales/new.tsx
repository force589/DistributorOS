import { ApiError, createIdempotencyKey, type SaleCreateRequest } from '@distributoros/api-client';
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
import { getSaleErrorTranslationKey } from '@/features/sales/errorMessages';
import { SaleForm } from '@/features/sales/SaleForm';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';
import { useDirtyFormGuard } from '@/navigation/UnsavedChangesContext';

export default function CreateSaleScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { pending, run } = useSingleFlightAction();
  const idempotencyKey = useRef(createIdempotencyKey());
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const leaveAfterSave = useDirtyFormGuard(dirty);

  const create = async (sale: SaleCreateRequest) => {
    await run(async () => {
      setError(null);
      setFieldErrors({});
      try {
        const result = await apiClient.createSale(sale, idempotencyKey.current);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['sales'] }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        leaveAfterSave(() => router.replace({
            pathname: '/sales/[saleNumber]',
            params: { saleNumber: result.sale.sale_number, notice: 'created' },
          }));
      } catch (createError) {
        if (createError instanceof ApiError) setFieldErrors(createError.fieldErrors);
        setError(t(getSaleErrorTranslationKey(createError, 'save')));
      }
    });
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo('/sales')}
        subtitle={t('sales.create.subtitle')}
        title={t('sales.create.title')}
      />
      {error ? (
        <View style={styles.feedback}>
          <FeedbackBanner message={error} />
        </View>
      ) : null}
      <SaleForm
        actionLabel={t('sales.create.action')}
        loading={pending}
        onDirtyChange={setDirty}
        loadingLabel={t('sales.create.loading')}
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
