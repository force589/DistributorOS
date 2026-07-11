import { Platform } from 'react-native';

import { businessDateIso } from '@/formatting/presentation';
import { shareBytes } from '@/platform/fileSharing';

export interface CsvSaveResult {
  uri: string;
  mode: 'downloaded' | 'shared';
}

export function csvFilename(reportName: string, businessDate = new Date()): string {
  const date = businessDateIso(businessDate);
  return `distributoros-${reportName}-report-${date}.csv`;
}

export async function saveCsvFile(filename: string, content: string): Promise<CsvSaveResult> {
  if (Platform.OS === 'web') {
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.style.display = 'none';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    return { mode: 'downloaded', uri: filename };
  }

  const bytes = new TextEncoder().encode(content);
  const buffer = bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength,
  ) as ArrayBuffer;
  await shareBytes(filename, buffer, 'text/csv', filename);
  return { mode: 'shared', uri: filename };
}
