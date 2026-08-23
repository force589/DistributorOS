import { useQuery } from '@tanstack/react-query';
import { useIsFocused, useLocalSearchParams, useRouter } from 'expo-router';
import { ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { apiClient } from '@/api/client';
import { FeedbackBanner } from '@/components/FeedbackBanner';
import { FullScreenState } from '@/components/FullScreenState';
import { PrimaryButton } from '@/components/PrimaryButton';
import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import { HeadingText } from '@/design-system';
import {
  formatInventoryDate,
  formatStockQuantity,
  lowStockStatusKeys,
} from '@/features/inventory/formatting';
import type { InventoryOperation } from '@/features/inventory/validation';

const operations: { operation: InventoryOperation; key: string }[] = [
  { operation: 'opening', key: 'inventory.operations.opening' },
  { operation: 'receipt', key: 'inventory.operations.receipt' },
  { operation: 'adjustment', key: 'inventory.operations.adjustment' },
  { operation: 'customerReturn', key: 'inventory.operations.customerReturn' },
  { operation: 'damage', key: 'inventory.operations.damage' },
  { operation: 'spoilage', key: 'inventory.operations.spoilage' },
];

export default function CurrentStockDetailsScreen() {
  const { t, i18n } = useTranslation();
  const isFocused = useIsFocused();
  const router = useRouter();
  const params = useLocalSearchParams<{ productCode: string; notice?: string }>();
  const productCode = Array.isArray(params.productCode)
    ? params.productCode[0]
    : params.productCode;
  const notice = Array.isArray(params.notice) ? params.notice[0] : params.notice;
  const query = useQuery({
    queryKey: ['inventory', 'current', productCode],
    queryFn: async ({ signal }) => {
      const product = await apiClient.getProductByCode(productCode, signal);
      const stock = await apiClient.getCurrentStock(product.id, undefined, signal);
      return { product, stock };
    },
    enabled: Boolean(productCode),
    subscribed: isFocused,
  });

  if (query.isPending) {
    return (
      <FullScreenState
        loading
        message={t('inventory.details.loadingMessage')}
        title={t('inventory.details.loadingTitle')}
      />
    );
  }
  if (query.isError || !query.data) {
    return (
      <FullScreenState
        actionLabel={t('common.back')}
        message={t('inventory.details.errorMessage')}
        onAction={() => router.replace('/inventory')}
        title={t('inventory.details.errorTitle')}
      />
    );
  }
  const { product, stock } = query.data;
  const details: [string, string][] = [
    [t('inventory.details.productCode'), stock.product_code],
    [t('inventory.details.warehouse'), stock.warehouse_name],
    [
      t('inventory.details.availableQuantity'),
      formatStockQuantity(stock.available_quantity, stock.unit, i18n.language, t),
    ],
    [
      t('inventory.details.lowStockThreshold'),
      formatStockQuantity(stock.low_stock_threshold, stock.unit, i18n.language, t),
    ],
    [t('inventory.details.stockStatus'), t(lowStockStatusKeys[stock.low_stock_status])],
    ...(stock.updated_at
      ? [[
          t('inventory.details.lastUpdated'),
          formatInventoryDate(stock.updated_at, i18n.language),
        ] as [string, string]]
      : []),
  ];

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo('/inventory')}
        title={t('inventory.details.title')}
      />
      <ScrollView contentContainerStyle={styles.content}>
        {notice === 'created' ? (
          <FeedbackBanner message={t('inventory.operations.success')} tone="success" />
        ) : null}
        <View style={styles.card}>
          <HeadingText level={2} style={styles.name}>{product.name}</HeadingText>
          <View style={styles.details}>
            {details.map(([label, value]) => (
              <View key={label} style={styles.detailRow}>
                <Text style={styles.detailLabel}>{label}</Text>
                <Text selectable style={styles.detailValue}>{value}</Text>
              </View>
            ))}
          </View>
        </View>
        <View style={styles.card}>
          <HeadingText level={2} style={styles.sectionTitle}>
            {t('inventory.details.operationsTitle')}
          </HeadingText>
          {operations.map(({ operation, key }) => (
            <PrimaryButton
              key={operation}
              destructive={operation === 'damage' || operation === 'spoilage'}
              disabled={operation === 'opening' && Boolean(stock.updated_at)}
              label={
                operation === 'opening' && stock.updated_at
                  ? t('inventory.operations.openingRecorded')
                  : t(key)
              }
              onPress={() => router.push({
                pathname: '/inventory/operation',
                params: { productCode: product.product_code, type: operation },
              })}
            />
          ))}
          {stock.updated_at ? (
            <Text style={styles.operationHelp}>
              {t('inventory.operations.openingRecordedHelp')}
            </Text>
          ) : null}
          <PrimaryButton
            label={t('inventory.details.history')}
            onPress={() => router.push({
              pathname: '/inventory/history',
              params: { productCode: product.product_code },
            })}
          />
        </View>
      </ScrollView>
    </SafeAreaView>
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
  sectionTitle: { color: colors.text, fontSize: 20, fontWeight: '800' },
  operationHelp: { color: colors.textMuted, fontSize: 13, lineHeight: 19 },
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
