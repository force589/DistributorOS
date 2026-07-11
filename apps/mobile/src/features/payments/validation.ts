import type { PaymentCreateRequest } from '@distributoros/api-client';

export interface PaymentAllocationDraft {
  invoiceId: string;
  reference: string;
  amount: string;
}

export interface PaymentDraft {
  customerId: string;
  customerName: string;
  paymentDate: string;
  amount: string;
  paymentMethod: PaymentCreateRequest['payment_method'];
  referenceNumber: string;
  notes: string;
  allocations: PaymentAllocationDraft[];
}

export type PaymentValidationKey =
  | 'payments.validation.customerRequired'
  | 'payments.validation.dateRequired'
  | 'payments.validation.dateInvalid'
  | 'payments.validation.amountRequired'
  | 'payments.validation.amountInvalid'
  | 'payments.validation.amountPositive'
  | 'payments.validation.amountPrecision'
  | 'payments.validation.amountTooLarge'
  | 'payments.validation.methodRequired'
  | 'payments.validation.referenceTooLong'
  | 'payments.validation.notesTooLong'
  | 'payments.validation.allocationAmountRequired'
  | 'payments.validation.allocationAmountInvalid'
  | 'payments.validation.allocationAmountPositive'
  | 'payments.validation.allocationAmountPrecision'
  | 'payments.validation.allocationTotalTooLarge'
  | 'payments.validation.duplicateAllocation';

export type PaymentValidationErrors = Record<string, PaymentValidationKey>;

const decimalPattern = /^(?:\d+(?:\.\d*)?|\.\d+)$/;

function validateMoney(
  value: string,
  kind: 'amount' | 'allocationAmount',
): PaymentValidationKey | undefined {
  const trimmed = value.trim();
  if (!trimmed) return `payments.validation.${kind}Required`;
  if (trimmed.startsWith('-') && Number.isFinite(Number(trimmed))) {
    return `payments.validation.${kind}Positive`;
  }
  if (!decimalPattern.test(trimmed) || !Number.isFinite(Number(trimmed))) {
    return `payments.validation.${kind}Invalid`;
  }
  if (Number(trimmed) <= 0) return `payments.validation.${kind}Positive`;
  if ((trimmed.split('.')[1]?.length ?? 0) > 2) {
    return `payments.validation.${kind}Precision`;
  }
  if (kind === 'amount' && Number(trimmed) > 9999999999999999.99) {
    return 'payments.validation.amountTooLarge';
  }
  return undefined;
}

function validIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().startsWith(value);
}

export function validatePayment(draft: PaymentDraft): PaymentValidationErrors {
  const errors: PaymentValidationErrors = {};
  if (!draft.customerId) errors.customer_id = 'payments.validation.customerRequired';
  if (!draft.paymentDate.trim()) errors.payment_date = 'payments.validation.dateRequired';
  else if (!validIsoDate(draft.paymentDate.trim())) {
    errors.payment_date = 'payments.validation.dateInvalid';
  }
  const amountError = validateMoney(draft.amount, 'amount');
  if (amountError) errors.amount = amountError;
  if (!draft.paymentMethod) errors.payment_method = 'payments.validation.methodRequired';
  if (draft.referenceNumber.trim().length > 120) {
    errors.reference_number = 'payments.validation.referenceTooLong';
  }
  if (draft.notes.trim().length > 1000) {
    errors.notes = 'payments.validation.notesTooLong';
  }
  const seen = new Set<string>();
  let allocationTotal = 0;
  draft.allocations.forEach((allocation, index) => {
    if (seen.has(allocation.invoiceId)) {
      errors.allocations = 'payments.validation.duplicateAllocation';
    }
    seen.add(allocation.invoiceId);
    const allocationError = validateMoney(allocation.amount, 'allocationAmount');
    if (allocationError) {
      errors[`allocations.${index}.allocated_amount`] = allocationError;
    } else {
      allocationTotal += Number(allocation.amount);
    }
  });
  if (!amountError && allocationTotal > Number(draft.amount)) {
    errors.allocations = 'payments.validation.allocationTotalTooLarge';
  }
  return errors;
}

export function normalizePayment(draft: PaymentDraft): PaymentCreateRequest {
  return {
    customer_id: draft.customerId,
    payment_date: draft.paymentDate.trim(),
    amount: draft.amount.trim(),
    payment_method: draft.paymentMethod,
    reference_number: draft.referenceNumber.trim() || undefined,
    notes: draft.notes.trim() || undefined,
    allocations: draft.allocations.map((allocation) => ({
      invoice_id: allocation.invoiceId,
      allocated_amount: allocation.amount.trim(),
    })),
  };
}
