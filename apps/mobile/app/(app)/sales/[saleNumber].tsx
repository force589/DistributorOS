import { ApiError, createIdempotencyKey, type ProductUnit, type SaleItem } from '@distributoros/api-client';
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
import { productUnitKeys } from '@/features/products/formatting';
import { getSaleErrorTranslationKey } from '@/features/sales/errorMessages';
import { formatInr, formatSaleDate, saleStatusKeys } from '@/features/sales/formatting';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';

export default function SaleDetailsScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useLocalSearchParams<{ saleNumber: string; notice?: string }>();
  const saleNumber = Array.isArray(params.saleNumber) ? params.saleNumber[0] : params.saleNumber;
  const notice = Array.isArray(params.notice) ? params.notice[0] : params.notice;
  const [confirmation, setConfirmation] = useState<'post' | 'void' | null>(null);
  const [feedback, setFeedback] = useState<string | null>(
    notice === 'created'
      ? t('sales.create.success')
      : notice === 'updated'
        ? t('sales.edit.success')
        : null,
  );
  const [error, setError] = useState<string | null>(null);
  const postKey = useRef(createIdempotencyKey());
  const voidKey = useRef(createIdempotencyKey());
  const { pending, run } = useSingleFlightAction();
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

  const sale = query.data;
  const changeStatus = async () => {
    if (!confirmation) return;
    await run(async () => {
      setError(null);
      setFeedback(null);
      try {
        const result = confirmation === 'post'
          ? await apiClient.postSale(sale.id, postKey.current)
          : await apiClient.voidSale(sale.id, voidKey.current);
        queryClient.setQueryData(['sale', saleNumber], result.sale);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['sales'] }),
          queryClient.invalidateQueries({ queryKey: ['inventory'] }),
          queryClient.invalidateQueries({
            queryKey: ['customer-financial-summary', sale.customer_id],
          }),
          queryClient.invalidateQueries({ queryKey: ['ledger', sale.customer_id] }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        setFeedback(t(confirmation === 'post' ? 'sales.post.success' : 'sales.void.success'));
        setConfirmation(null);
      } catch (statusError) {
        setError(
          statusError instanceof ApiError && statusError.code === 'INSUFFICIENT_STOCK'
            ? statusError.message
            : t(getSaleErrorTranslationKey(statusError, 'lifecycle')),
        );
        setConfirmation(null);
      }
    });
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        actionLabel={sale.status === 'DRAFT' ? t('sales.details.edit') : undefined}
        backLabel={t('common.back')}
        onAction={sale.status === 'DRAFT' ? () => router.push(`/sales/edit/${saleNumber}`) : undefined}
        onBack={() => router.dismissTo('/sales')}
        title={t('sales.details.title')}
      />
      <ScrollView contentContainerStyle={styles.content}>
        {feedback ? <FeedbackBanner message={feedback} tone="success" /> : null}
        {error ? <FeedbackBanner message={error} /> : null}
        {sale.status === 'POSTED' ? (
          <FeedbackBanner message={t('sales.details.postedNotice')} tone="success" />
        ) : null}
        {sale.status === 'VOID' ? <FeedbackBanner message={t('sales.details.voidNotice')} /> : null}
        <View style={styles.card}>
          <Text accessibilityRole="header" style={styles.saleNumber}>{sale.sale_number}</Text>
          <DetailRow label={t('sales.details.customer')} value={sale.customer_name} />
          <DetailRow label={t('sales.details.status')} value={t(saleStatusKeys[sale.status])} />
          <DetailRow
            label={t('sales.details.createdAt')}
            value={formatSaleDate(sale.created_at, i18n.language)}
          />
          <DetailRow
            label={t('sales.details.subtotal')}
            value={formatInr(sale.subtotal, i18n.language)}
          />
        </View>
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>{t('sales.details.items')}</Text>
          {sale.items.map((item) => (
            <ItemRow item={item} key={item.id} language={i18n.language} />
          ))}
        </View>
        {sale.status === 'DRAFT' ? (
          <PrimaryButton label={t('sales.post.action')} onPress={() => setConfirmation('post')} />
        ) : null}
        {sale.status === 'POSTED' ? (
          <PrimaryButton
            destructive
            label={t('sales.void.action')}
            onPress={() => setConfirmation('void')}
          />
        ) : null}
      </ScrollView>
      <ConfirmationDialog
        cancelLabel={t('common.cancel')}
        confirmLabel={t(confirmation === 'void' ? 'sales.void.confirm' : 'sales.post.confirm')}
        loading={pending}
        loadingLabel={t(confirmation === 'void' ? 'sales.void.loading' : 'sales.post.loading')}
        message={t(confirmation === 'void' ? 'sales.void.message' : 'sales.post.message')}
        onCancel={() => setConfirmation(null)}
        onConfirm={() => void changeStatus()}
        title={t(confirmation === 'void' ? 'sales.void.title' : 'sales.post.title')}
        visible={confirmation !== null}
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

function ItemRow({ item, language }: { item: SaleItem; language: string }) {
  const { t } = useTranslation();
  const unitKey = productUnitKeys[item.unit_snapshot as ProductUnit];
  return (
    <View style={styles.item}>
      <Text style={styles.itemName}>{item.product_name_snapshot}</Text>
      <View style={styles.itemValues}>
        <Text style={styles.itemText}>
          {t('sales.details.quantity')}: {item.quantity} {unitKey ? t(unitKey) : item.unit_snapshot}
        </Text>
        <Text style={styles.itemText}>
          {t('sales.details.unitPrice')}: {formatInr(item.unit_price, language)}
        </Text>
        <Text style={styles.itemTotal}>
          {t('sales.details.lineTotal')}: {formatInr(item.line_total, language)}
        </Text>
      </View>
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
  saleNumber: { color: colors.primary, fontSize: 26, fontWeight: '800' },
  sectionTitle: { color: colors.text, fontSize: 19, fontWeight: '800' },
  detailRow: {
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    gap: spacing.xs,
    paddingBottom: spacing.md,
  },
  detailLabel: { color: colors.textMuted, fontSize: 13, fontWeight: '700' },
  detailValue: { color: colors.text, fontSize: 16, lineHeight: 23 },
  item: {
    backgroundColor: colors.background,
    borderRadius: radii.md,
    gap: spacing.sm,
    padding: spacing.md,
  },
  itemName: { color: colors.text, fontSize: 17, fontWeight: '800' },
  itemValues: { gap: spacing.xs },
  itemText: { color: colors.textMuted, fontSize: 14 },
  itemTotal: { color: colors.text, fontSize: 15, fontWeight: '800' },
});
