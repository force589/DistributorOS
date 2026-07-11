import type {
  InventoryReportSort,
  LowStockReportSort,
  OutstandingReportSort,
  ReportPeriod,
  ReportStatus,
  SalesReportSort,
} from '@distributoros/api-client';

export type ReportKind = 'sales' | 'payments' | 'outstanding' | 'inventory' | 'low-stock';

export const reportKinds: ReportKind[] = [
  'sales',
  'payments',
  'outstanding',
  'inventory',
  'low-stock',
];

export const reportPeriods: ReportPeriod[] = [
  'all',
  'today',
  'yesterday',
  'this_week',
  'this_month',
  'custom',
];

export const salesStatuses: ReportStatus[] = ['all', 'draft', 'posted', 'void'];
export const paymentStatuses: ReportStatus[] = ['all', 'posted', 'void'];

export const datedReportSorts: SalesReportSort[] = [
  'newest',
  'oldest',
  'amount_desc',
  'amount_asc',
  'customer_asc',
  'customer_desc',
];

export const outstandingReportSorts: OutstandingReportSort[] = [
  'highest_outstanding',
  'alphabetical',
];

export const inventoryReportSorts: InventoryReportSort[] = [
  'name_asc',
  'name_desc',
  'stock_asc',
  'stock_desc',
  'value_asc',
  'value_desc',
];

export const lowStockReportSorts: LowStockReportSort[] = ['lowest_stock', 'alphabetical'];

export function isReportKind(value: string | undefined): value is ReportKind {
  return reportKinds.includes(value as ReportKind);
}

export function reportTitleKey(kind: ReportKind): string {
  return `insights.reports.types.${camelReportKey(kind)}.title`;
}

export function reportSubtitleKey(kind: ReportKind): string {
  return `insights.reports.types.${camelReportKey(kind)}.subtitle`;
}

export function camelReportKey(kind: ReportKind): string {
  return kind === 'low-stock' ? 'lowStock' : kind;
}
