import { ApiError } from '@distributoros/api-client';

import { getInvoiceErrorTranslationKey } from './errorMessages';

describe('invoice error localization', () => {
  it.each([
    ['INVOICE_NOT_FOUND', 'invoices.errors.notFound'],
    ['INVOICE_ALREADY_EXISTS', 'invoices.errors.alreadyExists'],
    ['INVOICE_ALREADY_ISSUED', 'invoices.errors.alreadyIssued'],
    ['INVOICE_ALREADY_VOIDED', 'invoices.errors.alreadyVoided'],
    ['INVOICE_NOT_ISSUED', 'invoices.errors.notIssued'],
    ['SALE_NOT_FOUND', 'invoices.errors.saleNotFound'],
    ['SALE_NOT_POSTED', 'invoices.errors.saleNotPosted'],
    ['CUSTOMER_ARCHIVED', 'invoices.errors.customerArchived'],
    ['SALE_ITEMS_REQUIRED', 'invoices.errors.itemsRequired'],
    ['INVALID_INVOICE_CURSOR', 'invoices.errors.invalidPage'],
    ['IDEMPOTENCY_KEY_REUSED', 'invoices.errors.submissionConflict'],
    ['INVOICE_STATE_CORRUPT', 'invoices.errors.corruptState'],
    ['NETWORK_ERROR', 'errors.network'],
  ])('maps %s to a stable localization key', (code, key) => {
    expect(getInvoiceErrorTranslationKey(new ApiError(400, code, 'ignored'))).toBe(key);
  });

  it('uses action-specific localized fallbacks', () => {
    expect(getInvoiceErrorTranslationKey(new Error('ignored'), 'save')).toBe(
      'invoices.errors.saveFailed',
    );
    expect(getInvoiceErrorTranslationKey(new Error('ignored'), 'lifecycle')).toBe(
      'invoices.errors.lifecycleFailed',
    );
    expect(getInvoiceErrorTranslationKey(new Error('ignored'), 'pdf')).toBe(
      'invoices.errors.pdfFailed',
    );
  });
});
