import { ApiError } from '@distributoros/api-client';

import { getErrorTranslationKey, type ErrorTranslationKey } from '@/features/auth/errorMessages';

export type InvoiceErrorTranslationKey =
  | ErrorTranslationKey
  | 'invoices.errors.notFound'
  | 'invoices.errors.alreadyExists'
  | 'invoices.errors.alreadyIssued'
  | 'invoices.errors.alreadyVoided'
  | 'invoices.errors.notIssued'
  | 'invoices.errors.saleNotFound'
  | 'invoices.errors.saleNotPosted'
  | 'invoices.errors.customerArchived'
  | 'invoices.errors.itemsRequired'
  | 'invoices.errors.invalidPage'
  | 'invoices.errors.submissionConflict'
  | 'invoices.errors.corruptState'
  | 'invoices.errors.saveFailed'
  | 'invoices.errors.loadFailed'
  | 'invoices.errors.lifecycleFailed'
  | 'invoices.errors.pdfFailed';

export function getInvoiceErrorTranslationKey(
  error: unknown,
  fallback: 'load' | 'save' | 'lifecycle' | 'pdf' = 'load',
): InvoiceErrorTranslationKey {
  if (error instanceof ApiError) {
    const key = {
      INVOICE_NOT_FOUND: 'invoices.errors.notFound',
      INVOICE_ALREADY_EXISTS: 'invoices.errors.alreadyExists',
      INVOICE_ALREADY_ISSUED: 'invoices.errors.alreadyIssued',
      INVOICE_ALREADY_VOIDED: 'invoices.errors.alreadyVoided',
      INVOICE_NOT_ISSUED: 'invoices.errors.notIssued',
      SALE_NOT_FOUND: 'invoices.errors.saleNotFound',
      SALE_NOT_POSTED: 'invoices.errors.saleNotPosted',
      CUSTOMER_ARCHIVED: 'invoices.errors.customerArchived',
      SALE_ITEMS_REQUIRED: 'invoices.errors.itemsRequired',
      INVALID_INVOICE_CURSOR: 'invoices.errors.invalidPage',
      IDEMPOTENCY_KEY_REUSED: 'invoices.errors.submissionConflict',
      INVOICE_STATE_CORRUPT: 'invoices.errors.corruptState',
    }[error.code] as InvoiceErrorTranslationKey | undefined;
    if (key) return key;
    const global = getErrorTranslationKey(error);
    if (global !== 'errors.unknown' && global !== 'errors.validation') return global;
  }
  if (fallback === 'save') return 'invoices.errors.saveFailed';
  if (fallback === 'lifecycle') return 'invoices.errors.lifecycleFailed';
  if (fallback === 'pdf') return 'invoices.errors.pdfFailed';
  return 'invoices.errors.loadFailed';
}
