import { isValidLedgerDate, ledgerEntryTypeKeys } from './formatting';

describe('ledger formatting', () => {
  it('maps implemented entry types to localization keys', () => {
    expect(ledgerEntryTypeKeys.SALE).toBe('ledger.entryTypes.sale');
    expect(ledgerEntryTypeKeys.REVERSAL).toBe('ledger.entryTypes.reversal');
    expect(ledgerEntryTypeKeys.PAYMENT).toBe('ledger.entryTypes.payment');
    expect(ledgerEntryTypeKeys.PAYMENT_REVERSAL).toBe('ledger.entryTypes.paymentReversal');
  });

  it.each([
    ['2026-06-29', true],
    ['2026-02-29', false],
    ['29-06-2026', false],
    ['', false],
  ])('validates ledger date %s', (value, expected) => {
    expect(isValidLedgerDate(value)).toBe(expected);
  });
});
