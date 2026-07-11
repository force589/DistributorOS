import type { InvoiceListItem } from '@distributoros/api-client';
import { Pressable, Text, type TextStyle, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import { formatInr } from '@/features/payments/formatting';

import { formatInvoiceDate, invoiceStatusKeys } from './formatting';

interface InvoiceListRowProps {
  item: InvoiceListItem;
  language: string;
  onPress: () => void;
}

const statusBadgeStyles = {
  DRAFT: 'badgeDRAFT',
  ISSUED: 'badgeISSUED',
  VOID: 'badgeVOID',
} satisfies Record<InvoiceListItem['status'], keyof typeof styles>;

export function InvoiceListRow({ item, language, onPress }: InvoiceListRowProps) {
  const { t } = useTranslation();
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.card}>
      <View style={styles.topRow}>
        <View style={styles.identity}>
          <Text style={styles.invoiceNumber}>{item.invoice_number}</Text>
          <Text style={styles.customer}>{item.customer_name}</Text>
        </View>
        <Text style={[styles.badge, styles[statusBadgeStyles[item.status]] as TextStyle]}>
          {t(invoiceStatusKeys[item.status])}
        </Text>
      </View>
      <View style={styles.metaRow}>
        <Text style={styles.total}>{formatInr(item.grand_total, language, item.currency)}</Text>
        <Text style={styles.muted}>{formatInvoiceDate(item.issue_date, language)}</Text>
      </View>
      <Text style={styles.muted}>
        {t('invoices.list.outstanding', {
          amount: formatInr(item.outstanding_amount, language, item.currency),
        })}
      </Text>
    </Pressable>
  );
}

const styles = ThemedStyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.md,
    borderWidth: 1,
    gap: spacing.sm,
    padding: spacing.md,
  },
  topRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: spacing.sm,
    justifyContent: 'space-between',
  },
  identity: { flex: 1, gap: spacing.xs },
  invoiceNumber: { color: colors.primary, fontSize: 14, fontWeight: '800' },
  customer: { color: colors.text, fontSize: 18, fontWeight: '700' },
  badge: {
    borderRadius: 999,
    fontSize: 12,
    fontWeight: '800',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  badgeDRAFT: { backgroundColor: colors.warningBackground, color: colors.warning },
  badgeISSUED: { backgroundColor: colors.successBackground, color: colors.success },
  badgeVOID: { backgroundColor: colors.dangerBackground, color: colors.danger },
  metaRow: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  total: { color: colors.text, fontSize: 17, fontWeight: '800' },
  muted: { color: colors.textMuted, fontSize: 13 },
});
