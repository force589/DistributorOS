import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
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
import { HeadingText } from '@/design-system';
import { getProductErrorTranslationKey } from '@/features/products/errorMessages';
import { formatInr, productUnitKeys } from '@/features/products/formatting';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';

export default function ProductDetailsScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useLocalSearchParams<{ productCode: string; notice?: string }>();
  const productCode = Array.isArray(params.productCode)
    ? params.productCode[0]
    : params.productCode;
  const notice = Array.isArray(params.notice) ? params.notice[0] : params.notice;
  const [confirmation, setConfirmation] = useState<'archive' | 'restore' | null>(null);
  const [feedback, setFeedback] = useState<string | null>(
    notice === 'created'
      ? t('products.create.success')
      : notice === 'updated'
        ? t('products.edit.success')
        : null,
  );
  const [error, setError] = useState<string | null>(null);
  const { pending, run } = useSingleFlightAction();
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
  const changeState = async () => {
    if (!confirmation) return;
    await run(async () => {
      setError(null);
      setFeedback(null);
      try {
        const result =
          confirmation === 'archive'
            ? await apiClient.archiveProduct(product.id)
            : await apiClient.restoreProduct(product.id);
        queryClient.setQueryData(['product', productCode], result.product);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['products'] }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        setFeedback(
          t(
            confirmation === 'archive'
              ? 'products.archive.success'
              : 'products.restore.success',
          ),
        );
        setConfirmation(null);
      } catch (stateError) {
        setError(t(getProductErrorTranslationKey(stateError, 'state')));
        setConfirmation(null);
      }
    });
  };

  const details: [string, string | null][] = [
    [t('products.fields.productCode'), product.product_code],
    [
      t('products.fields.status'),
      product.archived ? t('products.filters.archived') : t('products.details.active'),
    ],
    [t('products.fields.sellingPrice'), formatInr(product.selling_price, i18n.language)],
    [t('products.fields.unit'), t(productUnitKeys[product.unit])],
    [t('products.fields.sku'), product.sku],
    [t('products.fields.barcode'), product.barcode],
    [t('products.fields.category'), product.category],
    [t('products.fields.lowStockThreshold'), product.low_stock_threshold],
    [t('products.fields.description'), product.description],
  ];

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        actionLabel={t('products.details.edit')}
        backLabel={t('common.back')}
        onAction={() => router.push(`/products/edit/${product.product_code}`)}
        onBack={() => router.dismissTo('/products')}
        title={t('products.details.title')}
      />
      <ScrollView contentContainerStyle={styles.content}>
        {feedback ? <FeedbackBanner message={feedback} tone="success" /> : null}
        {error ? <FeedbackBanner message={error} /> : null}
        <View style={styles.card}>
          <HeadingText level={2} style={styles.name}>
            {product.name}
          </HeadingText>
          <View style={styles.details}>
            {details
              .filter(([, value]) => Boolean(value))
              .map(([label, value]) => (
                <DetailRow key={label} label={label} value={value ?? ''} />
              ))}
          </View>
          <PrimaryButton
            destructive={!product.archived}
            label={
              product.archived ? t('products.restore.action') : t('products.archive.action')
            }
            onPress={() => setConfirmation(product.archived ? 'restore' : 'archive')}
          />
        </View>
      </ScrollView>
      <ConfirmationDialog
        cancelLabel={t('common.cancel')}
        confirmLabel={
          confirmation === 'restore'
            ? t('products.restore.confirm')
            : t('products.archive.confirm')
        }
        loading={pending}
        loadingLabel={
          confirmation === 'restore'
            ? t('products.restore.loading')
            : t('products.archive.loading')
        }
        message={
          confirmation === 'restore'
            ? t('products.restore.message')
            : t('products.archive.message')
        }
        onCancel={() => setConfirmation(null)}
        onConfirm={() => void changeState()}
        title={
          confirmation === 'restore'
            ? t('products.restore.title')
            : t('products.archive.title')
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
  details: { gap: spacing.md },
  detailRow: {
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    gap: spacing.xs,
    paddingBottom: spacing.md,
  },
  detailLabel: { color: colors.textMuted, fontSize: 13, fontWeight: '700' },
  detailValue: { color: colors.text, fontSize: 16, lineHeight: 23 },
});
