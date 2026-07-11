import { createIdempotencyKey } from '@distributoros/api-client';
import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { apiClient } from '@/api/client';
import { FeedbackBanner } from '@/components/FeedbackBanner';
import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import { getInvoiceErrorTranslationKey } from '@/features/invoices/errorMessages';
import { formatInvoiceDateTime } from '@/features/invoices/formatting';
import { formatInr } from '@/features/payments/formatting';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';

export default function CreateInvoiceScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const idempotencyKey = useRef(createIdempotencyKey());
  const { pending, run } = useSingleFlightAction();
  const sales = useQuery({
    queryKey: ['invoices', 'posted-sale-picker', debouncedSearch],
    queryFn: ({ signal }) => apiClient.listSales({
      status: 'posted',
      search: debouncedSearch || undefined,
      limit: 25,
    }, signal),
    placeholderData: keepPreviousData,
  });

  const create = async (saleId: string) => {
    await run(async () => {
      setError(null);
      try {
        const result = await apiClient.createInvoice(
          { sale_id: saleId },
          idempotencyKey.current,
        );
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['invoices'] }),
          queryClient.invalidateQueries({
            queryKey: ['customer-invoices', result.invoice.customer_id],
          }),
          queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        ]);
        router.replace({
          pathname: '/invoices/[invoiceNumber]',
          params: { invoiceNumber: result.invoice.invoice_number, notice: 'created' },
        });
      } catch (createError) {
        setError(t(getInvoiceErrorTranslationKey(createError, 'save')));
      }
    });
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo('/invoices')}
        subtitle={t('invoices.create.subtitle')}
        title={t('invoices.create.title')}
      />
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        {error ? <FeedbackBanner message={error} /> : null}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>{t('invoices.create.selectSale')}</Text>
          <TextInput
            accessibilityLabel={t('invoices.create.searchLabel')}
            autoCapitalize="characters"
            onChangeText={setSearch}
            placeholder={t('invoices.create.searchPlaceholder')}
            placeholderTextColor={colors.textMuted}
            style={styles.input}
            value={search}
          />
          {sales.isFetching ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator color={colors.primary} />
              <Text style={styles.muted}>{t('invoices.create.loadingSales')}</Text>
            </View>
          ) : null}
          {sales.isError ? (
            <FeedbackBanner message={t(getInvoiceErrorTranslationKey(sales.error))} />
          ) : null}
          {!sales.isFetching && !sales.isError && sales.data?.items.length === 0 ? (
            <View style={styles.empty}>
              <Text style={styles.emptyTitle}>{t('invoices.create.emptyTitle')}</Text>
              <Text style={styles.emptyMessage}>{t('invoices.create.emptyMessage')}</Text>
            </View>
          ) : null}
          {sales.data?.items.map((sale) => (
            <Pressable
              accessibilityRole="button"
              disabled={pending}
              key={sale.id}
              onPress={() => void create(sale.id)}
              style={styles.saleOption}
            >
              <View style={styles.saleIdentity}>
                <Text style={styles.saleNumber}>{sale.sale_number}</Text>
                <Text style={styles.saleCustomer}>{sale.customer_name}</Text>
                <Text style={styles.muted}>
                  {formatInvoiceDateTime(sale.created_at, i18n.language)}
                </Text>
              </View>
              <Text style={styles.saleTotal}>{formatInr(sale.subtotal, i18n.language)}</Text>
            </Pressable>
          ))}
          {pending ? (
            <View style={styles.loadingRow}>
              <ActivityIndicator color={colors.primary} />
              <Text style={styles.muted}>{t('invoices.create.loading')}</Text>
            </View>
          ) : null}
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
  sectionTitle: { color: colors.text, fontSize: 18, fontWeight: '800' },
  input: {
    borderColor: colors.border,
    borderRadius: radii.md,
    borderWidth: 1,
    color: colors.text,
    fontSize: 16,
    minHeight: 48,
    paddingHorizontal: spacing.md,
  },
  loadingRow: { alignItems: 'center', flexDirection: 'row', gap: spacing.sm },
  muted: { color: colors.textMuted, fontSize: 13 },
  empty: { gap: spacing.sm, paddingVertical: spacing.lg },
  emptyTitle: { color: colors.text, fontSize: 18, fontWeight: '800' },
  emptyMessage: { color: colors.textMuted, fontSize: 14, lineHeight: 20 },
  saleOption: {
    alignItems: 'center',
    borderColor: colors.border,
    borderRadius: radii.md,
    borderWidth: 1,
    flexDirection: 'row',
    gap: spacing.md,
    justifyContent: 'space-between',
    padding: spacing.md,
  },
  saleIdentity: { flex: 1, gap: spacing.xs },
  saleNumber: { color: colors.primary, fontSize: 14, fontWeight: '800' },
  saleCustomer: { color: colors.text, fontSize: 16, fontWeight: '700' },
  saleTotal: { color: colors.text, fontSize: 16, fontWeight: '800' },
});
