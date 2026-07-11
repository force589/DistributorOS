import type { ProductCreateRequest } from '@distributoros/api-client';
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
import {
  getProductErrorTranslationKey,
  setProductUniqueFieldError,
} from '@/features/products/errorMessages';
import { ProductForm } from '@/features/products/ProductForm';
import type { ProductField } from '@/features/products/validation';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';
import { useDirtyFormGuard } from '@/navigation/UnsavedChangesContext';

export default function CreateProductScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { pending, run } = useSingleFlightAction();
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<ProductField, string>>>({});
  const [dirty, setDirty] = useState(false);
  const leaveAfterSave = useDirtyFormGuard(dirty);

  const create = async (product: ProductCreateRequest) => {
    await run(async () => {
      setError(null);
      setFieldErrors({});
      try {
        const result = await apiClient.createProduct(product);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['products'] }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        leaveAfterSave(() => router.replace({
            pathname: '/products/[productCode]',
            params: { productCode: result.product.product_code, notice: 'created' },
          }));
      } catch (createError) {
        setProductUniqueFieldError(createError, setFieldErrors, t);
        setError(t(getProductErrorTranslationKey(createError, 'save')));
      }
    });
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo('/products')}
        subtitle={t('products.create.subtitle')}
        title={t('products.create.title')}
      />
      {error ? (
        <View style={styles.feedback}>
          <FeedbackBanner message={error} />
        </View>
      ) : null}
      <ProductForm
        actionLabel={t('products.create.action')}
        loading={pending}
        onDirtyChange={setDirty}
        loadingLabel={t('products.create.loading')}
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
