import type { PaymentListItem } from '@distributoros/api-client';
import { Pressable, Text, type TextStyle, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';

import {
  formatInr,
  formatPaymentDate,
  paymentMethodKeys,
  paymentStatusKeys,
} from './formatting';

interface PaymentListRowProps {
  item: PaymentListItem;
  language: string;
  onPress: () => void;
}

const statusBadgeStyles = {
  POSTED: 'badgePOSTED',
  VOID: 'badgeVOID',
} satisfies Record<PaymentListItem['status'], keyof typeof styles>;

export function PaymentListRow({ item, language, onPress }: PaymentListRowProps) {
  const { t } = useTranslation();
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.card}>
      <View style={styles.topRow}>
        <View style={styles.identity}>
          <Text style={styles.paymentNumber}>{item.payment_number}</Text>
          <Text style={styles.customer}>{item.customer_name}</Text>
        </View>
        <Text style={[styles.badge, styles[statusBadgeStyles[item.status]] as TextStyle]}>
          {t(paymentStatusKeys[item.status])}
        </Text>
      </View>
      <View style={styles.metaRow}>
        <Text style={styles.total}>{formatInr(item.amount, language)}</Text>
        <Text style={styles.muted}>{t(paymentMethodKeys[item.payment_method])}</Text>
      </View>
      <Text style={styles.muted}>{formatPaymentDate(item.payment_date, language)}</Text>
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
  paymentNumber: { color: colors.primary, fontSize: 14, fontWeight: '800' },
  customer: { color: colors.text, fontSize: 18, fontWeight: '700' },
  badge: {
    borderRadius: 999,
    fontSize: 12,
    fontWeight: '800',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  badgePOSTED: { backgroundColor: colors.successBackground, color: colors.success },
  badgeVOID: { backgroundColor: colors.dangerBackground, color: colors.danger },
  metaRow: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  total: { color: colors.text, fontSize: 17, fontWeight: '800' },
  muted: { color: colors.textMuted, fontSize: 13 },
});
