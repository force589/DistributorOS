import { ApiError } from '@distributoros/api-client';

import { getInsightsErrorTranslationKey } from './errorMessages';

describe('insights API error localization', () => {
  it.each([
    ['GLOBAL_SEARCH_QUERY_REQUIRED', 'insights.errors.searchRequired'],
    ['REPORT_FILTER_INVALID', 'insights.errors.filterInvalid'],
    ['INVALID_REPORT_CURSOR', 'insights.errors.invalidCursor'],
    ['NETWORK_ERROR', 'errors.network'],
  ])('maps %s to a stable localization key', (code, key) => {
    expect(getInsightsErrorTranslationKey(new ApiError(400, code, 'failure'))).toBe(key);
  });

  it('uses action-specific report fallbacks', () => {
    expect(getInsightsErrorTranslationKey(new Error('failure'), 'dashboard')).toBe(
      'insights.errors.loadDashboard',
    );
    expect(getInsightsErrorTranslationKey(new Error('failure'), 'search')).toBe(
      'insights.errors.loadSearch',
    );
    expect(getInsightsErrorTranslationKey(new Error('failure'), 'csv')).toBe(
      'insights.errors.exportCsv',
    );
  });
});
