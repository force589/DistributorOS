import {
  createIdempotencyKey,
  type Invoice,
  type InvoiceItem,
  type ProductUnit,
} from '@distributoros/api-client';
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
import { HeadingText } from '@/design-system';
import { getInvoiceErrorTranslationKey } from '@/features/invoices/errorMessages';
import {
  formatInvoiceDate,
  formatInvoiceDateTime,
  invoiceStatusKeys,
} from '@/features/invoices/formatting';
import { formatInr } from '@/features/payments/formatting';
import { productUnitKeys } from '@/features/products/formatting';
import { formatNumber } from '@/formatting/presentation';
import { useSingleFlightAction } from '@/hooks/useSingleFlightAction';
import { openPdf, shareBytes } from '@/platform/fileSharing';

export default function InvoiceDetailsScreen() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useLocalSearchParams<{ invoiceNumber: string; notice?: string }>();
  const invoiceNumber = Array.isArray(params.invoiceNumber)
    ? params.invoiceNumber[0]
    : params.invoiceNumber;
  const notice = Array.isArray(params.notice) ? params.notice[0] : params.notice;
  const [confirmation, setConfirmation] = useState<'issue' | 'void' | null>(null);
  const [feedback, setFeedback] = useState<string | null>(
    notice === 'created' ? t('invoices.create.success') : null,
  );
  const [error, setError] = useState<string | null>(null);
  const [pdfAction, setPdfAction] = useState<'preview' | 'share' | null>(null);
  const issueKey = useRef(createIdempotencyKey());
  const voidKey = useRef(createIdempotencyKey());
  const { pending, run } = useSingleFlightAction();
  const query = useQuery({
    queryKey: ['invoice', invoiceNumber],
    queryFn: ({ signal }) => apiClient.getInvoiceByNumber(invoiceNumber, signal),
    enabled: Boolean(invoiceNumber),
  });

  if (query.isPending) {
    return (
      <FullScreenState
        loading
        message={t('invoices.details.loadingMessage')}
        title={t('invoices.details.loadingTitle')}
      />
    );
  }
  if (query.isError || !query.data) {
    return (
      <FullScreenState
        actionLabel={t('common.back')}
        message={t(getInvoiceErrorTranslationKey(query.error))}
        onAction={() => router.replace('/invoices')}
        title={t('invoices.details.errorTitle')}
      />
    );
  }

  const invoice = query.data;
  const address = [
    invoice.customer_address_line_1_snapshot,
    invoice.customer_address_line_2_snapshot,
    invoice.customer_city_snapshot,
    invoice.customer_state_snapshot,
    invoice.customer_postal_code_snapshot,
  ].filter(Boolean).join(', ');

  const invalidateInvoiceState = async (updated: Invoice) => {
    queryClient.setQueryData(['invoice', invoiceNumber], updated);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['invoices'] }),
      queryClient.invalidateQueries({ queryKey: ['customer-invoices', updated.customer_id] }),
      queryClient.invalidateQueries({ queryKey: ['payments'] }),
      queryClient.invalidateQueries({ queryKey: ['customer-payments', updated.customer_id] }),
      queryClient.invalidateQueries({
        queryKey: ['customer-financial-summary', updated.customer_id],
      }),
      queryClient.invalidateQueries({ queryKey: ['customer-balance', updated.customer_id] }),
      queryClient.invalidateQueries({ queryKey: ['customer-credit', updated.customer_id] }),
      queryClient.invalidateQueries({ queryKey: ['ledger', updated.customer_id] }),
      queryClient.invalidateQueries({ queryKey: ['sales'] }),
      queryClient.invalidateQueries({ queryKey: ['sale', updated.sale_number] }),
      queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
    ]);
  };

  const changeState = async () => {
    const action = confirmation;
    if (!action) return;
    await run(async () => {
      setError(null);
      setFeedback(null);
      try {
        const result = action === 'issue'
          ? await apiClient.issueInvoice(invoice.id, issueKey.current)
          : await apiClient.voidInvoice(invoice.id, voidKey.current);
        await invalidateInvoiceState(result.invoice);
        setFeedback(t(action === 'issue' ? 'invoices.issue.success' : 'invoices.void.success'));
        setConfirmation(null);
      } catch (stateError) {
        setError(t(getInvoiceErrorTranslationKey(stateError, 'lifecycle')));
        setConfirmation(null);
      }
    });
  };

  const handlePdf = async (action: 'preview' | 'share') => {
    setPdfAction(action);
    setError(null);
    setFeedback(null);
    try {
      const bytes = await apiClient.downloadInvoicePdf(invoice.id);
      const filename = `${invoice.invoice_number}.pdf`;
      if (action === 'preview') {
        await openPdf(filename, bytes);
      } else {
        await shareBytes(
          filename,
          bytes,
          'application/pdf',
          t('invoices.pdf.shareMessage', { invoiceNumber: invoice.invoice_number }),
        );
      }
      setFeedback(t(action === 'preview' ? 'invoices.pdf.previewSuccess' : 'invoices.pdf.shareSuccess'));
    } catch (pdfError) {
      setError(t(getInvoiceErrorTranslationKey(pdfError, 'pdf')));
    } finally {
      setPdfAction(null);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo('/invoices')}
        title={t('invoices.details.title')}
      />
      <ScrollView contentContainerStyle={styles.content}>
        {feedback ? <FeedbackBanner message={feedback} tone="success" /> : null}
        {error ? <FeedbackBanner message={error} /> : null}
        {invoice.status === 'DRAFT' ? (
          <FeedbackBanner message={t('invoices.details.draftNotice')} tone="warning" />
        ) : null}
        {invoice.status === 'VOID' ? (
          <FeedbackBanner message={t('invoices.details.voidNotice')} />
        ) : null}
        <View style={styles.card}>
          <HeadingText level={2} style={styles.invoiceNumber}>{invoice.invoice_number}</HeadingText>
          <DetailRow label={t('invoices.details.status')} value={t(invoiceStatusKeys[invoice.status])} />
          <DetailRow label={t('invoices.details.saleNumber')} value={invoice.sale_number} />
          <DetailRow
            label={t('invoices.details.issueDate')}
            value={formatInvoiceDate(invoice.issue_date, i18n.language)}
          />
          <DetailRow
            label={t('invoices.details.createdAt')}
            value={formatInvoiceDateTime(invoice.created_at, i18n.language)}
          />
          <DetailRow label={t('invoices.details.currency')} value={invoice.currency} />
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>{t('invoices.details.customer')}</Text>
          <DetailRow
            label={t('invoices.details.customerName')}
            value={invoice.customer_name_snapshot}
          />
          <DetailRow
            label={t('invoices.details.customerPhone')}
            value={invoice.customer_phone_snapshot || t('invoices.details.noPhone')}
          />
          <DetailRow
            label={t('invoices.details.customerAddress')}
            value={address || t('invoices.details.noAddress')}
          />
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>{t('invoices.details.items')}</Text>
          {invoice.items.map((item) => (
            <InvoiceItemRow currency={invoice.currency} item={item} key={item.id} language={i18n.language} />
          ))}
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>{t('invoices.details.totals')}</Text>
          <DetailRow label={t('invoices.details.subtotal')} value={formatInr(invoice.subtotal, i18n.language, invoice.currency)} />
          <DetailRow label={t('invoices.details.taxTotal')} value={formatInr(invoice.tax_total, i18n.language, invoice.currency)} />
          <DetailRow label={t('invoices.details.grandTotal')} value={formatInr(invoice.grand_total, i18n.language, invoice.currency)} />
          <DetailRow
            label={t('invoices.details.allocatedAmount')}
            value={formatInr(invoice.allocated_amount, i18n.language, invoice.currency)}
          />
          <DetailRow
            label={t('invoices.details.outstandingAmount')}
            value={formatInr(invoice.outstanding_amount, i18n.language, invoice.currency)}
          />
        </View>

        <View style={styles.actions}>
          <PrimaryButton
            label={t('invoices.pdf.preview')}
            loading={pdfAction === 'preview'}
            loadingLabel={t('invoices.pdf.previewLoading')}
            onPress={() => void handlePdf('preview')}
          />
          <PrimaryButton
            label={t('invoices.pdf.share')}
            loading={pdfAction === 'share'}
            loadingLabel={t('invoices.pdf.shareLoading')}
            onPress={() => void handlePdf('share')}
          />
          {invoice.status === 'DRAFT' ? (
            <PrimaryButton
              disabled={pending}
              label={t('invoices.issue.action')}
              onPress={() => setConfirmation('issue')}
            />
          ) : null}
          {invoice.status === 'ISSUED' ? (
            <PrimaryButton
              destructive
              disabled={pending}
              label={t('invoices.void.action')}
              onPress={() => setConfirmation('void')}
            />
          ) : null}
        </View>
      </ScrollView>
      <ConfirmationDialog
        cancelLabel={t('common.cancel')}
        confirmLabel={confirmation === 'issue' ? t('invoices.issue.confirm') : t('invoices.void.confirm')}
        loading={pending}
        loadingLabel={confirmation === 'issue' ? t('invoices.issue.loading') : t('invoices.void.loading')}
        message={confirmation === 'issue' ? t('invoices.issue.message') : t('invoices.void.message')}
        onCancel={() => setConfirmation(null)}
        onConfirm={() => void changeState()}
        title={confirmation === 'issue' ? t('invoices.issue.title') : t('invoices.void.title')}
        visible={confirmation !== null}
      />
    </SafeAreaView>
  );
}

function InvoiceItemRow({ item, language, currency }: { item: InvoiceItem; language: string; currency: string }) {
  const { t } = useTranslation();
  const unitKey = productUnitKeys[item.unit_snapshot as ProductUnit];
  return (
    <View style={styles.item}>
      <Text style={styles.itemName}>{item.product_snapshot}</Text>
      <View style={styles.itemGrid}>
        <MiniMetric
          label={t('invoices.details.quantity')}
          value={`${formatNumber(item.quantity_snapshot, language)} ${
            unitKey ? t(unitKey) : item.unit_snapshot
          }`}
        />
        <MiniMetric
          label={t('invoices.details.unitPrice')}
          value={formatInr(item.unit_price_snapshot, language, currency)}
        />
        <MiniMetric
          label={t('invoices.details.lineTotal')}
          value={formatInr(item.line_total, language, currency)}
        />
      </View>
    </View>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.miniMetric}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text selectable style={styles.miniMetricValue}>{value}</Text>
    </View>
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

const styles = ThemedStyleSheet.create({
  safeArea: { backgroundColor: colors.background, flex: 1 },
  content: {
    alignSelf: 'center',
    gap: spacing.md,
    maxWidth: 820,
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
  invoiceNumber: { color: colors.primary, fontSize: 28, fontWeight: '800' },
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
    gap: spacing.md,
    padding: spacing.md,
  },
  itemName: { color: colors.text, fontSize: 16, fontWeight: '800' },
  itemGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  miniMetric: {
    backgroundColor: colors.surface,
    borderRadius: radii.sm,
    flex: 1,
    gap: spacing.xs,
    minWidth: 140,
    padding: spacing.sm,
  },
  miniMetricValue: { color: colors.text, fontSize: 15, fontWeight: '800' },
  actions: { gap: spacing.md },
});
