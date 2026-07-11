import { paymentMethodKeys, paymentStatusKeys } from './formatting';

describe('payment formatting', () => {
  it('maps implemented payment statuses and methods to localization keys', () => {
    expect(paymentStatusKeys.POSTED).toBe('payments.status.posted');
    expect(paymentStatusKeys.VOID).toBe('payments.status.void');
    expect(paymentMethodKeys.cash).toBe('payments.methods.cash');
    expect(paymentMethodKeys.upi).toBe('payments.methods.upi');
    expect(paymentMethodKeys.bank_transfer).toBe('payments.methods.bankTransfer');
    expect(paymentMethodKeys.cheque).toBe('payments.methods.cheque');
    expect(paymentMethodKeys.other).toBe('payments.methods.other');
  });
});
