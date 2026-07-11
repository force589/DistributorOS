import { businessDateIso, formatLocalizedDate } from './presentation';

describe('timezone-safe presentation', () => {
  it('handles midnight boundaries and leap years', () => {
    expect(
      businessDateIso(new Date('2026-12-31T18:45:00Z'), 'Asia/Kolkata'),
    ).toBe('2027-01-01');
    expect(
      businessDateIso(new Date('2028-02-29T18:45:00Z'), 'Asia/Kolkata'),
    ).toBe('2028-03-01');
  });

  it('uses the browser Intl database for DST transitions', () => {
    const before = businessDateIso(
      new Date('2026-03-08T06:30:00Z'),
      'America/New_York',
    );
    const after = businessDateIso(
      new Date('2026-03-08T07:30:00Z'),
      'America/New_York',
    );
    expect(before).toBe('2026-03-08');
    expect(after).toBe('2026-03-08');
    expect(formatLocalizedDate('2028-02-29')).toBeTruthy();
  });
});
