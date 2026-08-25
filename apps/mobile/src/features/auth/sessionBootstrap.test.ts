import { ApiError, type ApiClient, type AuthResponse } from '@distributoros/api-client';

import type { AuthStorage } from './authStorage';
import { restoreSession } from './sessionBootstrap';
import { resetWebSessionCoordinatorForTests } from './webSessionCoordinator';

const session = {
  access_token: 'access',
  refresh_token: 'rotated',
  token_type: 'bearer',
  expires_in: 900,
  user: {
    id: '00000000-0000-0000-0000-000000000001',
    email: 'owner@example.com',
    business: {
      id: '00000000-0000-0000-0000-000000000002',
      business_name: 'Business A',
      currency: 'INR',
      language: 'en',
      theme: 'system',
      timezone: 'Asia/Kolkata',
    },
  },
} satisfies AuthResponse;

function storageWith(token: string | null) {
  return {
    getRefreshToken: jest.fn().mockResolvedValue(token),
    setRefreshToken: jest.fn().mockResolvedValue(undefined),
    clearRefreshToken: jest.fn().mockResolvedValue(undefined),
  } satisfies AuthStorage;
}

describe('session restoration', () => {
  afterEach(() => {
    resetWebSessionCoordinatorForTests();
  });

  it('restores and rotates a native refresh token', async () => {
    const storage = storageWith('stored-refresh');
    const api = { refresh: jest.fn().mockResolvedValue(session) } as unknown as ApiClient;

    await expect(restoreSession({ api, storage, platform: 'android' })).resolves.toEqual(session);
    expect(api.refresh).toHaveBeenCalledWith('stored-refresh');
    expect(storage.setRefreshToken).toHaveBeenCalledWith('rotated');
  });

  it('restores a web session from the HttpOnly refresh cookie without JS token storage', async () => {
    const webSession = { ...session, refresh_token: null } satisfies AuthResponse;
    const storage = storageWith(null);
    const api = { refresh: jest.fn().mockResolvedValue(webSession) } as unknown as ApiClient;

    await expect(restoreSession({ api, storage, platform: 'web' })).resolves.toEqual(webSession);
    expect(api.refresh).toHaveBeenCalledWith(null);
    expect(storage.setRefreshToken).not.toHaveBeenCalled();
  });

  it('treats authoritative web refresh expiry as anonymous', async () => {
    const storage = storageWith(null);
    const api = {
      refresh: jest.fn().mockRejectedValue(new ApiError(401, 'SESSION_EXPIRED', 'Expired')),
    } as unknown as ApiClient;

    await expect(restoreSession({ api, storage, platform: 'web' })).resolves.toBeNull();
    expect(api.refresh).toHaveBeenCalledWith(null);
    expect(storage.clearRefreshToken).toHaveBeenCalledTimes(1);
  });

  it('does not convert temporary web refresh failures into logout', async () => {
    const storage = storageWith(null);
    const api = {
      refresh: jest.fn().mockRejectedValue(
        new ApiError(0, 'NETWORK_ERROR', 'The server could not be reached.'),
      ),
    } as unknown as ApiClient;

    await expect(restoreSession({ api, storage, platform: 'web' })).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
    });
    expect(api.refresh).toHaveBeenCalledWith(null);
    expect(storage.clearRefreshToken).not.toHaveBeenCalled();
  });

  it('clears an expired session without treating it as an anonymous success', async () => {
    const storage = storageWith('expired-refresh');
    const api = {
      refresh: jest.fn().mockRejectedValue(new ApiError(401, 'SESSION_EXPIRED', 'Expired')),
    } as unknown as ApiClient;

    await expect(restoreSession({ api, storage, platform: 'android' })).resolves.toBeNull();
    expect(storage.clearRefreshToken).toHaveBeenCalledTimes(1);
  });
});
