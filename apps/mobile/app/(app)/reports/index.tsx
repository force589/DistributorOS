import { type Href, useRouter } from 'expo-router';
import { Fragment } from 'react';
import {
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { ScreenHeader } from '@/components/ScreenHeader';
import { appIcons, type AppIconName } from '@/design/icons';
import { useResponsiveLayout } from '@/design/responsive';
import { useTheme } from '@/design/theme';
import { Card, Divider, HeadingText, NavigationListItem } from '@/design-system';
import {
  reportKinds,
  reportSubtitleKey,
  reportTitleKey,
  type ReportKind,
} from '@/features/insights/reportDefinitions';

const reportIcons: Record<ReportKind, AppIconName> = {
  sales: appIcons.sales,
  payments: appIcons.payments,
  outstanding: appIcons.customers,
  inventory: appIcons.inventory,
  'low-stock': appIcons.reports,
};

export default function ReportsIndexScreen() {
  const { t } = useTranslation();
  const router = useRouter();
  const responsive = useResponsiveLayout();
  const theme = useTheme();

  return (
    <SafeAreaView style={{ backgroundColor: theme.colors.background, flex: 1 }}>
      <ScreenHeader
        backLabel={t('common.back')}
        onBack={() => router.dismissTo('/(app)')}
        subtitle={t('insights.reports.subtitle')}
        title={t('insights.reports.title')}
      />
      <ScrollView
        contentContainerStyle={{
          alignItems: 'center',
          gap: theme.spacing.md,
          paddingBottom: theme.spacing.xxl,
          paddingHorizontal: responsive.isPhone ? theme.spacing.md : theme.spacing.lg,
          paddingTop: theme.spacing.lg,
        }}
      >
        <View style={{ gap: theme.spacing.md, maxWidth: responsive.isDesktop ? 980 : 760, width: '100%' }}>
          <Card style={{ gap: theme.spacing.sm }}>
            <HeadingText level={2} style={[theme.typography.heading, { color: theme.colors.text }]}>
              {t('insights.reports.readOnlyTitle')}
            </HeadingText>
            <Text style={[theme.typography.body, { color: theme.colors.textMuted }]}>
              {t('insights.reports.readOnlyMessage')}
            </Text>
          </Card>
          <Card style={{ overflow: 'hidden', padding: theme.spacing.sm }}>
            {reportKinds.map((kind, index) => (
              <Fragment key={kind}>
                <ReportRow
                  kind={kind}
                  onPress={() => router.push(`/reports/${kind}` as Href)}
                />
                {index < reportKinds.length - 1 ? <Divider /> : null}
              </Fragment>
            ))}
          </Card>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function ReportRow({ kind, onPress }: { kind: ReportKind; onPress: () => void }) {
  const { t } = useTranslation();
  return (
    <NavigationListItem
      icon={reportIcons[kind]}
      onPress={onPress}
      subtitle={t(reportSubtitleKey(kind))}
      title={t(reportTitleKey(kind))}
    />
  );
}
