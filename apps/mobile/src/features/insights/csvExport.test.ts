import { csvFilename } from './csvExport';

describe('CSV export helpers', () => {
  it('creates stable tenant-neutral report filenames', () => {
    expect(csvFilename('sales', new Date('2026-06-30T12:00:00Z'))).toBe(
      'distributoros-sales-report-2026-06-30.csv',
    );
  });
});
