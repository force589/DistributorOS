import { Platform } from 'react-native';

export type AppEnvironment = 'development' | 'preview' | 'production';

const appEnvironment = (process.env.EXPO_PUBLIC_APP_ENV ?? 'development') as AppEnvironment;
const apiUrl = Platform.OS === 'android'
  ? process.env.EXPO_PUBLIC_ANDROID_API_URL
  : Platform.OS === 'ios'
    ? process.env.EXPO_PUBLIC_IOS_API_URL
    : Platform.OS === 'web'
      ? process.env.EXPO_PUBLIC_WEB_API_URL
      : process.env.EXPO_PUBLIC_API_URL;

if (!['development', 'preview', 'production'].includes(appEnvironment)) {
  throw new Error(
    'EXPO_PUBLIC_APP_ENV must be development, preview, or production.',
  );
}

if (!apiUrl) {
  throw new Error(`An API URL is required for the ${Platform.OS} platform.`);
}

export function validateApiUrl(
  value: string,
  platform: string,
  targetEnvironment: AppEnvironment,
): void {
  if (platform === 'web') return;
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error(
      `The ${platform} API URL must be an absolute http or https URL.`,
    );
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error(
      `The ${platform} API URL must use http or https.`,
    );
  }
  if (targetEnvironment !== 'development' && parsed.protocol !== 'https:') {
    throw new Error('Preview and production native API URLs must use HTTPS.');
  }
}

validateApiUrl(apiUrl, Platform.OS, appEnvironment);

export const environment = {
  appEnvironment,
  apiUrl,
} as const;
