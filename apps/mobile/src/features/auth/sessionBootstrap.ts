import { ApiError, type ApiClient, type AuthResponse } from '@distributoros/api-client';

import type { AuthStorage } from './authStorage';
import { coordinateWebRefresh } from './webSessionCoordinator';

interface RestoreSessionOptions {
  api: ApiClient;
  storage: AuthStorage;
  platform: string;
}

export async function restoreSession({
  api,
  storage,
  platform,
}: RestoreSessionOptions): Promise<AuthResponse | null> {
  const refreshToken = await storage.getRefreshToken();
  if (platform !== 'web' && !refreshToken) {
    return null;
  }
  try {
    const session = platform === 'web'
      ? await coordinateWebRefresh(() => api.refresh(null))
      : await api.refresh(refreshToken);
    if (!session) return null;
    if (session.refresh_token) {
      await storage.setRefreshToken(session.refresh_token);
    }
    return session;
  } catch (error) {
    if (
      error instanceof ApiError &&
      ['SESSION_EXPIRED', 'AUTHENTICATION_REQUIRED'].includes(error.code)
    ) {
      await storage.clearRefreshToken();
      return null;
    }
    throw error;
  }
}
