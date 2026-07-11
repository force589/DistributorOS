import { normalizePayment, type PaymentDraft, validatePayment } from './validation';

const validPayment: PaymentDraft = {
  customerId: 'customer-1',
  customerName: 'Mango Corner',
  paymentDate: '2026-06-30',
  amount: '1500.50',
  paymentMethod: 'upi',
  referenceNumber: ' UPI-123 ',
  notes: ' Morning collection ',
  allocations: [
    {
      invoiceId: 'invoice-1',
      reference: 'INV-000001',
      amount: '500.50',
    },
  ],
};

describe('payment validation', () => {
  it('accepts valid payment information', () => {
    expect(validatePayment(validPayment)).toEqual({});
  });

  it('returns field-specific keys for every payment rule', () => {
    expect(
      validatePayment({
        customerId: '',
        customerName: '',
        paymentDate: '2026-02-29',
        amount: '0',
        paymentMethod: '' as PaymentDraft['paymentMethod'],
        referenceNumber: 'x'.repeat(121),
        notes: 'x'.repeat(1001),
        allocations: [
          { invoiceId: 'invoice-1', reference: 'INV-000001', amount: '1.001' },
          { invoiceId: 'invoice-1', reference: 'INV-000001', amount: '' },
        ],
      }),
    ).toEqual({
      customer_id: 'payments.validation.customerRequired',
      payment_date: 'payments.validation.dateInvalid',
      amount: 'payments.validation.amountPositive',
      payment_method: 'payments.validation.methodRequired',
      reference_number: 'payments.validation.referenceTooLong',
      notes: 'payments.validation.notesTooLong',
      allocations: 'payments.validation.duplicateAllocation',
      'allocations.0.allocated_amount': 'payments.validation.allocationAmountPrecision',
      'allocations.1.allocated_amount': 'payments.validation.allocationAmountRequired',
    });
  });

  it('prevents allocating more than the payment amount', () => {
    expect(validatePayment({
      ...validPayment,
      amount: '50',
      allocations: [
        { invoiceId: 'invoice-1', reference: 'INV-000001', amount: '25.00' },
        { invoiceId: 'invoice-2', reference: 'INV-000002', amount: '25.01' },
      ],
    })).toMatchObject({
      allocations: 'payments.validation.allocationTotalTooLarge',
    });
  });

  it('normalizes optional fields and allocation payloads', () => {
    expect(normalizePayment(validPayment)).toMatchObject({
      customer_id: 'customer-1',
      payment_date: '2026-06-30',
      amount: '1500.50',
      payment_method: 'upi',
      reference_number: 'UPI-123',
      notes: 'Morning collection',
      allocations: [
        {
          invoice_id: 'invoice-1',
          allocated_amount: '500.50',
        },
      ],
    });
  });
});
