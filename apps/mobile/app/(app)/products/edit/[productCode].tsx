import type { ProductCreateRequest } from '@distributoros/api-client';
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
import {
  getProductErrorTranslationKey,
  setProductUniqueFieldError,
} from '@/features/products/errorMessages';
import { ProductForm } from '@/features/products/ProductForm';
import type { ProductField } from '@/features/products/validation';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';
import { useDirtyFormGuard } from '@/navigation/UnsavedChangesContext';

export default function EditProductScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useLocalSearchParams<{ productCode: string }>();
  const productCode = Array.isArray(params.productCode)
    ? params.productCode[0]
    : params.productCode;
  const { pending, run } = useSingleFlightAction();
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<ProductField, string>>>({});
  const [dirty, setDirty] = useState(false);
  const leaveAfterSave = useDirtyFormGuard(dirty);
  const query = useQuery({
    queryKey: ['product', productCode],
    queryFn: ({ signal }) => apiClient.getProductByCode(productCode, signal),
    enabled: Boolean(productCode),
  });

  if (query.isPending) {
    return (
      <FullScreenState
        loading
        message={t('products.details.loadingMessage')}
        title={t('products.details.loadingTitle')}
      />
    );
  }
  if (query.isError || !query.data) {
    return (
      <FullScreenState
        actionLabel={t('common.back')}
        message={t('products.details.errorMessage')}
        onAction={() => router.replace('/products')}
        title={t('products.details.errorTitle')}
      />
    );
  }

  const product = query.data;
  const save = async (changes: ProductCreateRequest) => {
    await run(async () => {
      setError(null);
      setFieldErrors({});
      try {
        const result = await apiClient.updateProduct(product.id, changes);
        queryClient.setQueryData(['product', productCode], result.product);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['products'] }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        leaveAfterSave(() => router.replace({
            pathname: '/products/[productCode]',
            params: { productCode: result.product.product_code, notice: 'updated' },
          }));
      } catch (saveError) {
        setProductUniqueFieldError(saveError, setFieldErrors, t);
        setError(t(getProductErrorTranslationKey(saveError, 'save')));
      }
    });
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo(`/products/${product.product_code}`)}
        subtitle={t('products.edit.subtitle')}
        title={t('products.edit.title')}
      />
      {error ? (
        <View style={styles.feedback}>
          <FeedbackBanner message={error} />
        </View>
      ) : null}
      <ProductForm
        actionLabel={t('products.edit.action')}
        initialProduct={product}
        loading={pending}
        onDirtyChange={setDirty}
        loadingLabel={t('products.edit.loading')}
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
