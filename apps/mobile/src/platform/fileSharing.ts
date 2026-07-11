import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import { Linking, Platform } from 'react-native';

const base64Alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

export type FileDeliveryMode = 'downloaded' | 'opened' | 'shared';

export function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let output = '';
  for (let index = 0; index < bytes.length; index += 3) {
    const byte1 = bytes[index] ?? 0;
    const byte2 = bytes[index + 1] ?? 0;
    const byte3 = bytes[index + 2] ?? 0;
    const triplet = (byte1 << 16) | (byte2 << 8) | byte3;
    output += base64Alphabet.charAt((triplet >> 18) & 0x3f);
    output += base64Alphabet.charAt((triplet >> 12) & 0x3f);
    output += index + 1 < bytes.length ? base64Alphabet.charAt((triplet >> 6) & 0x3f) : '=';
    output += index + 2 < bytes.length ? base64Alphabet.charAt(triplet & 0x3f) : '=';
  }
  return output;
}

export function downloadWebFile(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function shareBytes(
  filename: string,
  buffer: ArrayBuffer,
  mimeType: string,
  dialogTitle: string,
): Promise<FileDeliveryMode> {
  if (Platform.OS === 'web') {
    const blob = new Blob([buffer], { type: mimeType });
    if (
      typeof navigator !== 'undefined' &&
      typeof File !== 'undefined' &&
      typeof navigator.share === 'function' &&
      typeof navigator.canShare === 'function'
    ) {
      const file = new File([blob], filename, { type: mimeType });
      if (navigator.canShare({ files: [file] })) {
        try {
          await navigator.share({ files: [file], title: dialogTitle });
          return 'shared';
        } catch (error) {
          if (error instanceof DOMException && error.name === 'AbortError') throw error;
        }
      }
    }
    downloadWebFile(filename, blob);
    return 'downloaded';
  }

  const uri = await writeTemporaryFile(filename, arrayBufferToBase64(buffer));
  try {
    if (!(await Sharing.isAvailableAsync())) throw new Error('FILE_SHARING_UNAVAILABLE');
    await Sharing.shareAsync(uri, { dialogTitle, mimeType });
    return 'shared';
  } finally {
    await FileSystem.deleteAsync(uri, { idempotent: true });
  }
}

export async function openPdf(filename: string, buffer: ArrayBuffer): Promise<FileDeliveryMode> {
  if (Platform.OS === 'web') {
    const blob = new Blob([buffer], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    const opened = window.open(url, '_blank', 'noopener,noreferrer');
    if (!opened) {
      downloadWebFile(filename, blob);
      return 'downloaded';
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    return 'opened';
  }

  const uri = await writeTemporaryFile(filename, arrayBufferToBase64(buffer));
  const openUri = Platform.OS === 'android' ? await FileSystem.getContentUriAsync(uri) : uri;
  await Linking.openURL(openUri);
  setTimeout(() => {
    void FileSystem.deleteAsync(uri, { idempotent: true });
  }, 60_000);
  return 'opened';
}

async function writeTemporaryFile(filename: string, base64: string): Promise<string> {
  if (!FileSystem.cacheDirectory) throw new Error('FILE_CACHE_UNAVAILABLE');
  const safeName = filename.replace(/[^a-zA-Z0-9._-]/g, '-');
  const uri = `${FileSystem.cacheDirectory}${Date.now()}-${safeName}`;
  await FileSystem.writeAsStringAsync(uri, base64, {
    encoding: FileSystem.EncodingType.Base64,
  });
  return uri;
}
