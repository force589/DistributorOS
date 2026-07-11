import { type Href, useRouter } from 'expo-router';
import {
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { ScreenHeader } from '@/components/ScreenHeader';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import {
  reportKinds,
  reportSubtitleKey,
  reportTitleKey,
  type ReportKind,
} from '@/features/insights/reportDefinitions';

export default function ReportsIndexScreen() {
  const { t } = useTranslation();
  const router = useRouter();

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo('/(app)')}
        subtitle={t('insights.reports.subtitle')}
        title={t('insights.reports.title')}
      />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.intro}>
          <Text style={styles.introTitle}>{t('insights.reports.readOnlyTitle')}</Text>
          <Text style={styles.introMessage}>{t('insights.reports.readOnlyMessage')}</Text>
        </View>
        {reportKinds.map((kind) => (
          <ReportCard
            key={kind}
            kind={kind}
            onPress={() => router.push(`/reports/${kind}` as Href)}
          />
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

function ReportCard({ kind, onPress }: { kind: ReportKind; onPress: () => void }) {
  const { t } = useTranslation();
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.card}>
      <View style={styles.cardText}>
        <Text style={styles.cardTitle}>{t(reportTitleKey(kind))}</Text>
        <Text style={styles.cardSubtitle}>{t(reportSubtitleKey(kind))}</Text>
      </View>
      <Text style={styles.open}>{t('insights.reports.open')}</Text>
    </Pressable>
  );
}

const styles = ThemedStyleSheet.create({
  safeArea: {
    backgroundColor: colors.background,
    flex: 1,
  },
  content: {
    gap: spacing.md,
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  intro: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.lg,
    borderWidth: 1,
    gap: spacing.sm,
    padding: spacing.lg,
  },
  introTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  introMessage: {
    color: colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
  },
  card: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.lg,
    borderWidth: 1,
    flexDirection: 'row',
    gap: spacing.md,
    justifyContent: 'space-between',
    padding: spacing.lg,
  },
  cardText: {
    flex: 1,
    gap: spacing.xs,
  },
  cardTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  cardSubtitle: {
    color: colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
  },
  open: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: '800',
  },
});
