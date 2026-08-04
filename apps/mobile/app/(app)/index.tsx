import type { Dashboard, RecentActivityItem } from '@distributoros/api-client';
import { useQuery } from '@tanstack/react-query';
import { type Href, useRouter } from 'expo-router';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';

import { apiClient } from '@/api/client';
import { FullScreenState } from '@/components/FullScreenState';
import { appIcons, type AppIconName } from '@/design/icons';
import { StyleSheet as ThemedStyleSheet } from '@/design/stylesheet';
import { colors, radii, spacing } from '@/design/tokens';
import { useResponsiveLayout } from '@/design/responsive';
import { useTheme } from '@/design/theme';
import { ActionCard, SectionHeader } from '@/design-system';
import { useAuth } from '@/features/auth/AuthContext';
import { getInsightsErrorTranslationKey } from '@/features/insights/errorMessages';
import {
  formatDateTime,
  formatMoney,
  formatQuantity,
} from '@/features/insights/formatting';

const quickActions: { key: string; icon: AppIconName; href: Href }[] = [
  { key: 'customers', icon: appIcons.customers, href: '/customers' },
  { key: 'products', icon: appIcons.products, href: '/products' },
  { key: 'inventory', icon: appIcons.inventory, href: '/inventory' },
  { key: 'sales', icon: appIcons.sales, href: '/sales' },
  { key: 'payments', icon: appIcons.payments, href: '/payments' },
  { key: 'invoices', icon: appIcons.invoices, href: '/invoices' },
];

export default function DashboardScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const responsive = useResponsiveLayout();
  const router = useRouter();
  const { user } = useAuth();

  const dashboard = useQuery({
    queryKey: ['dashboard'],
    queryFn: ({ signal }) => apiClient.getDashboard(signal),
  });

  if (dashboard.isPending) {
    return (
      <FullScreenState
        loading
        message={t('insights.dashboard.loadingMessage')}
        title={t('insights.dashboard.loadingTitle')}
      />
    );
  }

  if (dashboard.isError) {
    return (
      <FullScreenState
        actionLabel={t('common.retry')}
        message={t(getInsightsErrorTranslationKey(dashboard.error, 'dashboard'))}
        onAction={() => void dashboard.refetch()}
        title={t('insights.dashboard.errorTitle')}
      />
    );
  }

  const data = dashboard.data;
  const quickActionWidth =
    responsive.quickActionColumns === 4
      ? '23.5%'
      : responsive.quickActionColumns === 3
        ? '31%'
        : '47.5%';

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: theme.colors.background }]}>
      <ScrollView
        contentContainerStyle={{
          alignItems: 'center',
          paddingBottom: theme.spacing.xxl,
          paddingHorizontal: responsive.isPhone ? theme.spacing.md : theme.spacing.lg,
          paddingTop: responsive.isPhone ? theme.spacing.md : theme.spacing.lg,
        }}
        refreshControl={
          <RefreshControl
            onRefresh={() => void dashboard.refetch()}
            refreshing={dashboard.isRefetching}
            tintColor={theme.colors.primary}
          />
        }
      >
        <View style={{ gap: theme.spacing.lg, maxWidth: responsive.contentMaxWidth, width: '100%' }}>
          <View style={[styles.header, { paddingRight: theme.spacing.xxxl }]}>
            <View>
              <Text style={[styles.brand, { color: theme.colors.primary }]}>{t('brand.name')}</Text>
              <Text style={[styles.subtitle, { color: theme.colors.textMuted }]}>
                {t('insights.dashboard.subtitle', {
                  business: user?.business.business_name,
                  date: data.business_date,
                })}
              </Text>
            </View>
            {dashboard.isFetching ? <ActivityIndicator color={theme.colors.primary} /> : null}
          </View>

          <View style={styles.metricGrid}>
            <MetricCard title={t('insights.metrics.todaySales')} value={formatMoney(data.today_sales.value)} />
            <MetricCard
              title={t('insights.metrics.todayCollections')}
              value={formatMoney(data.today_collections.value)}
            />
            <MetricCard
              title={t('insights.metrics.outstandingReceivables')}
              value={formatMoney(data.outstanding_receivables.value)}
            />
            <MetricCard
              title={t('insights.metrics.customerCredit')}
              value={formatMoney(data.customer_credit.value)}
            />
            <MetricCard
              title={t('insights.metrics.totalCustomers')}
              value={formatQuantity(data.total_customers.value)}
            />
            <MetricCard
              title={t('insights.metrics.activeProducts')}
              value={formatQuantity(data.active_products.value)}
            />
            <MetricCard
              title={t('insights.metrics.inventoryValue')}
              value={formatMoney(data.inventory_value.value)}
            />
            <MetricCard
              title={t('insights.metrics.lowStockProducts')}
              value={formatQuantity(data.low_stock_products.value)}
            />
            <MetricCard
              title={t('insights.metrics.outOfStockProducts')}
              value={formatQuantity(data.out_of_stock_products.value)}
            />
          </View>

          <View style={{ gap: theme.spacing.sm }}>
            <SectionHeader title={t('home.quickActions')} />
            <View style={styles.actionGrid}>
              {quickActions.map((action) => (
                <ActionCard
                  description={t(`home.modules.${action.key}.description`)}
                  icon={action.icon}
                  key={action.key}
                  onPress={() => router.navigate(action.href as Href)}
                  style={{ width: quickActionWidth }}
                  testID={`quick-action-${action.key}`}
                  title={t(`home.modules.${action.key}.title`)}
                />
              ))}
            </View>
          </View>

          <ActivitySection
            emptyMessage={t('insights.dashboard.emptyRecentSales')}
            items={data.recent_sales}
            statusGroup="sales"
            title={t('insights.dashboard.recentSales')}
            onPress={(path) => router.push(path as Href)}
          />
          <ActivitySection
            emptyMessage={t('insights.dashboard.emptyRecentPayments')}
            items={data.recent_payments}
            statusGroup="payments"
            title={t('insights.dashboard.recentPayments')}
            onPress={(path) => router.push(path as Href)}
          />
          <ActivitySection
            emptyMessage={t('insights.dashboard.emptyRecentInvoices')}
            items={data.recent_invoices}
            statusGroup="invoices"
            title={t('insights.dashboard.recentInvoices')}
            onPress={(path) => router.push(path as Href)}
          />
          <InventoryActivity dashboard={data} />
          <TopSelling dashboard={data} />
          <Outstanding dashboard={data} onPress={(customerCode) => router.push(`/customers/${customerCode}`)} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function MetricCard({ title, value }: { title: string; value: string }) {
  const theme = useTheme();
  return (
    <View style={[styles.metricCard, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
      <Text style={[styles.metricTitle, { color: theme.colors.textMuted }]}>{title}</Text>
      <Text style={[styles.metricValue, { color: theme.colors.text }]}>{value}</Text>
    </View>
  );
}

function ActivitySection({
  emptyMessage,
  items,
  onPress,
  statusGroup,
  title,
}: {
  emptyMessage: string;
  items: RecentActivityItem[];
  onPress: (path: string) => void;
  statusGroup: 'sales' | 'payments' | 'invoices';
  title: string;
}) {
  const { t } = useTranslation();
  return (
    <View style={styles.section}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>{title}</Text>
      {items.length ? items.map((item) => {
        const status = t(`${statusGroup}.status.${camelStatus(item.status)}`);
        return (
          <Pressable
            accessibilityRole="button"
            key={item.id}
            onPress={() => onPress(item.detail_path)}
            style={styles.row}
          >
            <View style={styles.rowText}>
              <Text style={styles.rowTitle}>{item.number}</Text>
              <Text style={styles.rowSubtitle}>{item.customer ?? status}</Text>
            </View>
            <View style={styles.rowTrailing}>
              <Text style={styles.rowAmount}>{item.amount ? formatMoney(item.amount) : status}</Text>
              <Text style={styles.rowTime}>{formatDateTime(item.occurred_at)}</Text>
            </View>
          </Pressable>
        );
      }) : <Text style={styles.emptyText}>{emptyMessage}</Text>}
    </View>
  );
}

function InventoryActivity({ dashboard }: { dashboard: Dashboard }) {
  const { t } = useTranslation();
  return (
    <View style={styles.section}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>
        {t('insights.dashboard.recentInventory')}
      </Text>
      {dashboard.recent_inventory_activity.length ? dashboard.recent_inventory_activity.map((item) => (
        <View key={item.id} style={styles.row}>
          <View style={styles.rowText}>
            <Text style={styles.rowTitle}>{item.product}</Text>
            <Text style={styles.rowSubtitle}>
              {t(`inventory.movementTypes.${camelStatus(item.status)}`)}
            </Text>
          </View>
          <View style={styles.rowTrailing}>
            <Text style={styles.rowAmount}>{formatQuantity(item.quantity, item.unit)}</Text>
            <Text style={styles.rowTime}>{formatDateTime(item.occurred_at)}</Text>
          </View>
        </View>
      )) : <Text style={styles.emptyText}>{t('insights.dashboard.emptyRecentInventory')}</Text>}
    </View>
  );
}

function camelStatus(value: string): string {
  return value.toLowerCase().replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
}

function TopSelling({ dashboard }: { dashboard: Dashboard }) {
  const { t } = useTranslation();
  return (
    <View style={styles.section}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>
        {t('insights.dashboard.topSellingProducts')}
      </Text>
      {dashboard.top_selling_products.length ? dashboard.top_selling_products.map((item) => (
        <View key={item.product_id} style={styles.row}>
          <View style={styles.rowText}>
            <Text style={styles.rowTitle}>{item.product_name}</Text>
            <Text style={styles.rowSubtitle}>{item.product_code}</Text>
          </View>
          <View style={styles.rowTrailing}>
            <Text style={styles.rowAmount}>{formatMoney(item.total_sales)}</Text>
            <Text style={styles.rowTime}>{formatQuantity(item.quantity_sold)}</Text>
          </View>
        </View>
      )) : <Text style={styles.emptyText}>{t('insights.dashboard.emptyTopSellingProducts')}</Text>}
    </View>
  );
}

function Outstanding({
  dashboard,
  onPress,
}: {
  dashboard: Dashboard;
  onPress: (customerCode: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <View style={styles.section}>
      <Text accessibilityRole="header" style={styles.sectionTitle}>
        {t('insights.dashboard.highestOutstandingCustomers')}
      </Text>
      {dashboard.highest_outstanding_customers.length ? dashboard.highest_outstanding_customers.map((item) => (
        <Pressable
          accessibilityRole="button"
          key={item.customer_id}
          onPress={() => onPress(item.customer_code)}
          style={styles.row}
        >
          <View style={styles.rowText}>
            <Text style={styles.rowTitle}>{item.customer_name}</Text>
            <Text style={styles.rowSubtitle}>{item.customer_code}</Text>
          </View>
          <Text style={styles.rowAmount}>{formatMoney(item.outstanding_balance)}</Text>
        </Pressable>
      )) : <Text style={styles.emptyText}>{t('insights.dashboard.emptyOutstandingCustomers')}</Text>}
    </View>
  );
}

const styles = ThemedStyleSheet.create({
  safeArea: {
    backgroundColor: colors.background,
    flex: 1,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  brand: {
    color: colors.primary,
    fontSize: 26,
    fontWeight: '800',
  },
  subtitle: {
    color: colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
    marginTop: spacing.xs,
  },
  actionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  metricGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  metricCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.lg,
    borderWidth: 1,
    flexGrow: 1,
    minWidth: 150,
    padding: spacing.md,
  },
  metricTitle: {
    color: colors.textMuted,
    fontSize: 13,
    fontWeight: '700',
  },
  metricValue: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '800',
    marginTop: spacing.sm,
  },
  section: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: radii.lg,
    borderWidth: 1,
    gap: spacing.sm,
    padding: spacing.md,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  row: {
    alignItems: 'center',
    borderTopColor: colors.border,
    borderTopWidth: 1,
    flexDirection: 'row',
    gap: spacing.md,
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
  },
  rowText: {
    flex: 1,
    gap: spacing.xs,
  },
  rowTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  rowSubtitle: {
    color: colors.textMuted,
    fontSize: 13,
  },
  rowTrailing: {
    alignItems: 'flex-end',
    gap: spacing.xs,
  },
  rowAmount: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '800',
  },
  rowTime: {
    color: colors.textMuted,
    fontSize: 12,
  },
  emptyText: {
    color: colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
  },
});
