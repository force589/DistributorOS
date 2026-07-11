import { ApiError } from '@distributoros/api-client';

import { getErrorTranslationKey, type ErrorTranslationKey } from '@/features/auth/errorMessages';

export type InsightsErrorTranslationKey =
  | ErrorTranslationKey
  | 'insights.errors.searchRequired'
  | 'insights.errors.filterInvalid'
  | 'insights.errors.invalidCursor'
  | 'insights.errors.loadDashboard'
  | 'insights.errors.loadSearch'
  | 'insights.errors.loadReport'
  | 'insights.errors.exportCsv';

export function getInsightsErrorTranslationKey(
  error: unknown,
  fallback: 'dashboard' | 'search' | 'report' | 'csv' = 'report',
): InsightsErrorTranslationKey {
  if (error instanceof ApiError) {
    const key = {
      GLOBAL_SEARCH_QUERY_REQUIRED: 'insights.errors.searchRequired',
      REPORT_FILTER_INVALID: 'insights.errors.filterInvalid',
      INVALID_REPORT_CURSOR: 'insights.errors.invalidCursor',
    }[error.code] as InsightsErrorTranslationKey | undefined;
    if (key) return key;
    const global = getErrorTranslationKey(error);
    if (global !== 'errors.unknown' && global !== 'errors.validation') return global;
  }
  if (fallback === 'dashboard') return 'insights.errors.loadDashboard';
  if (fallback === 'search') return 'insights.errors.loadSearch';
  if (fallback === 'csv') return 'insights.errors.exportCsv';
  return 'insights.errors.loadReport';
}
