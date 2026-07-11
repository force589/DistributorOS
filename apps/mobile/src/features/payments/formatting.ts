import type { PaymentListItem, PaymentMethod, PaymentStatus } from '@distributoros/api-client';
import {
  formatCurrency,
  formatLocalizedDate,
  getActiveCurrency,
} from '@/formatting/presentation';

export const paymentStatusKeys: Record<Exclude<PaymentStatus, 'all'> | 'POSTED' | 'VOID', string> = {
  posted: 'payments.status.posted',
  void: 'payments.status.void',
  POSTED: 'payments.status.posted',
  VOID: 'payments.status.void',
};

export const paymentMethodKeys: Record<Exclude<PaymentMethod, 'all'>, string> = {
  cash: 'payments.methods.cash',
  upi: 'payments.methods.upi',
  bank_transfer: 'payments.methods.bankTransfer',
  cheque: 'payments.methods.cheque',
  other: 'payments.methods.other',
};

export function formatInr(value: string, language: string, currency: string = getActiveCurrency()): string {
  return formatCurrency(value, currency, language);
}

export function formatPaymentDate(value: string, language: string): string {
  return formatLocalizedDate(value, language, {
    dateStyle: 'medium',
  });
}

export function formatPaymentDateTime(value: string, language: string): string {
  return formatLocalizedDate(value, language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

export function paymentRowKey(payment: PaymentListItem): string {
  return payment.payment_number;
}
